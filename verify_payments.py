"""Company collection lifecycle using temporary native registrations and memory mail only."""
import json
import os
import uuid
from datetime import timedelta
from unittest.mock import patch
import copy
import base64
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit

os.environ['PYTEST_CURRENT_TEST'] = 'verify_payments'
from indico.web.flask.app import make_app
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.modules.events import Event
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.registration.util import create_personal_data_fields
from indico.util.date_time import now_utc

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)
suffix = uuid.uuid4().hex[:10]
users, event_id = [], None
from yujian_site import payments as p
from yujian_site import YujianSitePlugin
with app.app_context():
    settings_type = type(YujianSitePlugin.settings)
real_get, real_set = settings_type.get, settings_type.set
company = copy.deepcopy(p.COMPANY_DEFAULT)


def settings_get(self, name, *args, **kwargs):
    if self.module == 'plugin_yujian_site' and name == 'company_payments':
        return copy.deepcopy(company)
    return real_get(self, name, *args, **kwargs)


def settings_set(self, name, value, *args, **kwargs):
    if self.module == 'plugin_yujian_site' and name == 'company_payments':
        company.clear()
        company.update(copy.deepcopy(value))
        return
    return real_set(self, name, value, *args, **kwargs)


get_patch, set_patch = patch.object(settings_type, 'get', settings_get), patch.object(settings_type, 'set', settings_set)
get_patch.start()
set_patch.start()


def client_for(user_id):
    client = app.test_client()
    with app.app_context(), client.session_transaction() as session:
        session.set_session_user(User.get(user_id))
    token = json.loads(client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']
    return client, {'X-CSRF-Token': token}


try:
    assert p.total(SimpleNamespace(price=Decimal('0.30000000000000004'))) == '0.30', 'Native float-priced option sums must normalize to cents'
    with app.test_request_context():
        for role in ('finance', 'organizer', 'attendee', 'other'):
            user = create_user(f'payments-{role}-{suffix}@conference.test',
                               {'first_name': '收费验收', 'last_name': role},
                               Identity(provider='indico', identifier=f'payments-{role}-{suffix}', password=uuid.uuid4().hex))
            user.is_admin = role == 'finance'
            db.session.flush()
            users.append(user.id)
        db.session.commit()
    finance, fh = client_for(users[0])
    organizer, oh = client_for(users[1])
    attendee, ah = client_for(users[2])
    other, xh = client_for(users[3])
    assert finance.get('/api/company/payments/').status_code == 200, 'Company collection settings must exist'
    assert organizer.get('/api/company/payments/').status_code == 403
    assert app.test_client().get('/api/company/payments/').status_code == 401
    account = {'enabled': True, 'revision': 0, 'account_name': '遇见科技验收账户（禁止汇款）',
               'bank_name': '验收银行（非真实账户）', 'account_number': '000000000000', 'contact': '测试联系人'}
    assert finance.put('/api/company/payments/', json=account).status_code == 400, 'CSRF must remain required'
    account['enabled'] = 'yes'
    assert finance.put('/api/company/payments/', json=account, headers=fh).status_code == 400
    account['enabled'] = True
    assert finance.put('/api/company/payments/', json=account, headers=fh).status_code == 200
    assert finance.put('/api/company/payments/', json=account, headers=fh).status_code == 409, 'Stale settings revision'
    created = organizer.post('/api/conferences/', json={
        'title': f'收费闭环验收 {suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
        'location': '武汉', 'description': '仅测试收费，禁止实际汇款。', 'template': 'academic-full'}, headers=oh)
    assert created.status_code == 201
    event_id = created.json['id']
    with app.test_request_context():
        event = Event.get(event_id)
        form = RegistrationForm(event=event, title='普通参会票', currency='CNY',
                                start_dt=now_utc() - timedelta(days=1), end_dt=now_utc() + timedelta(days=2),
                                require_login=True, require_captcha=False, moderation_enabled=True,
                                notification_sender_address='no-reply@example.invalid')
        create_personal_data_fields(form)
        db.session.add(form)
        db.session.commit()
        form_id = form.id
    fee_url = f'/api/conferences/{event_id}/fees'
    assert other.put(fee_url, json={'form_id': form_id, 'base_price': '100.00'}, headers=xh).status_code == 403
    for value in ['NaN', 'Infinity', '-1', '1.001', '1000000000', True, {}, None]:
        assert organizer.put(fee_url, json={'form_id': form_id, 'base_price': value}, headers=oh).status_code == 400, value
    assert organizer.put(fee_url, json={'form_id': form_id, 'base_price': '0.00', 'conditions': ''}, headers=oh).status_code == 400, 'Paid options also require nonempty conditions'
    assert organizer.put(fee_url, json={'form_id': form_id, 'base_price': '100.00', 'conditions': '测试收费说明：全额退款需公司财务审核。'}, headers=oh).status_code == 200
    assert organizer.post(f'/api/conferences/{event_id}/publication', json={'published': True}, headers=oh).status_code == 200
    registration_ids = []
    for client, headers, user_id, role in ((attendee, ah, users[2], 'attendee'), (other, xh, users[3], 'other')):
        sent = client.post(f'/event/{event_id}/registrations/{form_id}/', json={
            'first_name': '收费验收', 'last_name': role, 'email': f'payments-{role}-{suffix}@conference.test',
            'affiliation': '验收'}, headers=headers)
        assert sent.status_code == 200 and 'redirect' in sent.json, (sent.status_code, sent.get_data(as_text=True)[:500])
        with app.app_context():
            reg = Registration.query.filter_by(registration_form_id=form_id, user_id=user_id).one()
            registration_ids.append(reg.id)
        rid = registration_ids[-1]
        assert client.post(f'/api/payments/{rid}/create', json={}, headers=headers).status_code == 409, 'Approval precedes payment'
        approved = organizer.post(f'/event/{event_id}/manage/registration/{form_id}/registrations/{rid}/approve', headers=oh)
        assert approved.status_code == 200
        detail = client.get(f'/api/payments/{rid}/').json
        assert detail['order']['amount'] == '100.00' and detail['registration_state'] == 'unpaid'
    rid, other_rid = registration_ids
    detail_url = f'/api/payments/{rid}/'
    def action(client, headers, name, payload):
        return client.post(detail_url + name, json=payload, headers=headers)
    assert other.get(detail_url).status_code == 403
    assert attendee.get(f'/api/conferences/{event_id}/orders').status_code == 403
    assert other.get(f'/api/conferences/{event_id}/orders').status_code == 403
    assert other.get(f'/payments/{rid}/receipt/').status_code == 403
    assert action(attendee, ah, 'transfer', {'payer': '验收付款人', 'reference': '自报流水'}).status_code == 400
    assert action(attendee, ah, 'checkout', {'provider': 'wechat', 'accepted_terms': True}).status_code == 503
    assert action(attendee, ah, 'checkout', {'provider': 'alipay', 'accepted_terms': True}).status_code == 503
    assert action(attendee, ah, 'transfer', {'payer': '验收付款人', 'reference': '自报流水', 'amount': '0.01', 'accepted_terms': True}).status_code == 200
    assert attendee.get(detail_url).json['order']['status'] == 'review'
    assert attendee.get(detail_url).json['registration_state'] == 'unpaid', 'A claim must not mark paid'
    assert action(organizer, oh, 'confirm', {'reference': 'bank-' + suffix, 'amount': '100.00'}).status_code == 403
    assert action(attendee, ah, 'confirm', {'reference': 'bank-' + suffix, 'amount': '100.00'}).status_code == 403
    assert organizer.post(f'/event/{event_id}/manage/registration/{form_id}/registrations/{rid}/toggle-payment', headers=oh).status_code == 403
    assert action(finance, fh, 'confirm', {'reference': 'bank-' + suffix, 'amount': '1.00'}).status_code == 409
    for _ in range(2):
        paid = action(finance, fh, 'confirm', {'reference': 'bank-' + suffix, 'amount': '100.00'})
        assert paid.status_code == 200, (paid.status_code, paid.get_data(as_text=True)[:500])
    with app.app_context():
        assert len(Registration.get(rid).transactions) == 1
    assert attendee.get(detail_url).json['registration_state'] == 'complete'
    duplicate = finance.post(f'/api/payments/{other_rid}/confirm', json={'reference': 'bank-' + suffix, 'amount': '100.00'}, headers=fh)
    assert duplicate.status_code == 409, 'Bank reference cannot pay two orders'
    receipt = attendee.get(f'/payments/{rid}/receipt/')
    assert receipt.status_code == 200 and '不是税务发票' in receipt.get_data(as_text=True)
    assert 'no-store' in receipt.headers['Cache-Control']
    invoice = {'kind': 'company', 'title': '测试公司', 'tax_id': '91310000TEST0000000', 'email': 'billing@example.com'}
    assert action(attendee, ah, 'invoice', invoice).status_code == 200
    assert action(organizer, oh, 'invoice-issued', {'number': 'INV-' + suffix}).status_code == 403
    assert action(finance, fh, 'invoice-issued', {'number': 'INV-' + suffix}).status_code == 200
    assert action(attendee, ah, 'refund', {'reason': '行程取消'}).status_code == 200
    assert action(finance, fh, 'refund-decision', {'action': 'reject', 'note': '请补充资料'}).status_code == 200
    assert action(attendee, ah, 'refund', {'reason': '已补充资料'}).status_code == 200
    assert action(finance, fh, 'refund-decision', {'action': 'confirm', 'amount': '99.00', 'reference': 'refund-' + suffix, 'note': '银行已退'}).status_code == 409
    for _ in range(2):
        refunded = action(finance, fh, 'refund-decision', {'action': 'confirm', 'amount': '100.00', 'reference': 'refund-' + suffix, 'note': '银行已全额退款，原发票已红冲'})
        assert refunded.status_code == 200
    result = attendee.get(detail_url).json
    assert result['order']['status'] == 'refunded' and result['registration_state'] == 'withdrawn'
    assert result['order']['invoice']['number'] == 'INV-' + suffix
    assert action(finance, fh, 'refund-decision', {'action': 'confirm', 'amount': '100.00', 'reference': 'different-refund', 'note': '另一次'}).status_code == 409
    deleted = organizer.post(f'/event/{event_id}/manage/registration/{form_id}/registrations/delete', data={'registration_id': str(rid)}, headers=oh)
    assert deleted.status_code == 409, ('Financial registration deletion must be blocked', deleted.status_code)
    assert organizer.post(f'/event/{event_id}/manage/registration/{form_id}/delete', headers=oh).status_code == 409
    from indico.core import signals
    from werkzeug.exceptions import Conflict
    with app.test_request_context():
        reg = Registration.get(rid)
        try:
            signals.event.registration_deleted.send(reg, permanent=True)
            raise AssertionError('Permanent purge of an order registration must be blocked')
        except Conflict:
            pass
        db.session.rollback()
        reg = Registration.get(rid)
        reg.is_deleted = True
        try:
            p.ensure_order(reg)
            raise AssertionError('Deleted registrations cannot create or reuse orders')
        except Conflict:
            pass
        db.session.rollback()
    with app.app_context():
        assert len(Registration.get(rid).transactions) == 2
    export = organizer.get(f'/api/conferences/{event_id}/orders.csv')
    assert export.status_code == 200 and 'attachment' in export.headers['Content-Disposition']
    assert 'refund-' + suffix in export.get_data(as_text=True)
    orders = organizer.get(f'/api/conferences/{event_id}/orders').json
    assert orders['total'] == 2 and orders['can_confirm'] is False
    assert 'audit' in next(item for item in orders['items'] if item['registration_id'] == rid)['order']
    assert 'audit' not in result['order'], 'Do not expose internal operator history to participants'
    # Exercise real RSA verification and AES-GCM decryption; only the outgoing HTTP transport is fake.
    from yujian_site import payment_gateways as gateway
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    with tempfile.TemporaryDirectory() as directory:
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path, public_path = Path(directory) / 'private.pem', Path(directory) / 'public.pem'
        private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        public_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        merchant = {'alipay': {'enabled': True, 'app_id': 'test-app', 'seller_id': 'test-seller',
                              'private_key_path': str(private_path), 'alipay_public_key_path': str(public_path)},
                    'wechat': {'enabled': True, 'appid': 'test-app', 'mchid': 'test-merchant',
                               'serial_no': 'test-serial', 'platform_key_id': 'test-platform', 'api_v3_key': '0' * 32,
                               'private_key_path': str(private_path), 'platform_public_key_path': str(public_path)}}
        def signed(value):
            return base64.b64encode(private.sign(value.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
        def alipay(fields):
            values = {**fields, 'sign_type': 'RSA2'}
            values['sign'] = signed('&'.join(f'{k}={v}' for k, v in sorted(values.items()) if k != 'sign_type'))
            return app.test_client().post('/api/payments/notify/alipay', data=values)
        with patch.object(gateway, 'merchant_config', return_value=merchant), patch.object(gateway, 'config', SimpleNamespace(BASE_URL='https://payments.example.com')):
            started = other.post(f'/api/payments/{other_rid}/checkout', json={'provider': 'alipay', 'accepted_terms': True}, headers=xh)
            assert started.status_code == 200, ('alipay checkout', started.status_code)
            query = {key: values[0] for key, values in parse_qs(urlsplit(started.json['url']).query).items()}
            private.public_key().verify(base64.b64decode(query.pop('sign')), '&'.join(f'{k}={v}' for k, v in sorted(query.items())).encode(), padding.PKCS1v15(), hashes.SHA256())
            assert json.loads(query['biz_content'])['total_amount'] == '100.00'
            assert other.post(f'/api/payments/{other_rid}/transfer', json={'payer': 'x', 'reference': 'x', 'accepted_terms': True}, headers=xh).status_code == 409
            number = other.get(f'/api/payments/{other_rid}/').json['order']['number']
            fields = {'app_id': 'test-app', 'seller_id': 'test-seller', 'trade_status': 'TRADE_SUCCESS',
                      'out_trade_no': number, 'trade_no': 'alipay-' + suffix, 'total_amount': '100.00'}
            assert app.test_client().post('/api/payments/notify/alipay', data={**fields, 'sign_type': 'RSA2', 'sign': 'fake'}).status_code == 400
            assert alipay({**fields, 'seller_id': 'attacker'}).status_code == 400
            assert alipay({**fields, 'total_amount': '1.00'}).status_code == 409
            with ThreadPoolExecutor(max_workers=2) as executor:
                notifications = list(executor.map(lambda _: alipay(fields), range(2)))
            for notified in notifications:
                assert notified.status_code == 200 and notified.get_data(as_text=True) == 'success'
            with app.app_context():
                assert len(Registration.get(other_rid).transactions) == 1
                event = Event.get(event_id)
                wechat_form = RegistrationForm(event=event, title='微信验收票', base_price=100, currency='CNY',
                    start_dt=now_utc()-timedelta(days=1), end_dt=now_utc()+timedelta(days=2), require_login=True,
                    require_captcha=False, notification_sender_address='no-reply@example.invalid')
                create_personal_data_fields(wechat_form)
                db.session.add(wechat_form)
                db.session.commit()
                wechat_form_id = wechat_form.id
            posted = other.post(f'/event/{event_id}/registrations/{wechat_form_id}/', json={
                'first_name': '收费验收', 'last_name': 'other', 'email': f'payments-other-{suffix}@conference.test', 'affiliation': '验收'}, headers=xh)
            assert posted.status_code == 200
            with app.app_context():
                wechat_id = Registration.query.filter_by(registration_form_id=wechat_form_id, user_id=users[3]).one().id
            def signed_headers(raw):
                timestamp, nonce = str(int(time.time())), uuid.uuid4().hex
                return {'Wechatpay-Timestamp': timestamp, 'Wechatpay-Nonce': nonce, 'Wechatpay-Serial': 'test-platform',
                        'Wechatpay-Signature': signed(f'{timestamp}\n{nonce}\n{raw}\n')}
            def fake_post(url, **kwargs):
                assert url == 'https://api.mch.weixin.qq.com/v3/pay/transactions/native'
                assert json.loads(kwargs['data'])['amount'] == {'total': 10000, 'currency': 'CNY'}
                assert kwargs['allow_redirects'] is False and kwargs['timeout'] == (5, 15)
                raw = json.dumps({'code_url': 'weixin://wxpay/bizpayurl?pr=TESTONLY'})
                return SimpleNamespace(text=raw, headers=signed_headers(raw), status_code=200, json=lambda: json.loads(raw))
            with patch.object(gateway.requests, 'post', side_effect=fake_post) as transport:
                started = other.post(f'/api/payments/{wechat_id}/checkout', json={'provider': 'wechat', 'accepted_terms': True}, headers=xh)
                assert started.status_code == 200 and started.json['qr'].startswith('data:image/png;base64,')
                assert other.post(f'/api/payments/{wechat_id}/checkout', json={'provider': 'wechat', 'accepted_terms': True}, headers=xh).status_code == 200
                assert transport.call_count == 1, 'Repeated checkout reuses the same order'
            number = other.get(f'/api/payments/{wechat_id}/').json['order']['number']
            def wechat(values, *, bad_signature=False, stale=False):
                nonce, associated = '0123456789ab', 'transaction'
                ciphertext = AESGCM(b'0'*32).encrypt(nonce.encode(), json.dumps(values).encode(), associated.encode())
                raw = json.dumps({'event_type': 'TRANSACTION.SUCCESS', 'resource': {'algorithm': 'AEAD_AES_256_GCM',
                    'nonce': nonce, 'associated_data': associated, 'ciphertext': base64.b64encode(ciphertext).decode()}})
                headers = signed_headers(raw)
                if bad_signature: headers['Wechatpay-Signature'] = 'fake'
                if stale: headers['Wechatpay-Timestamp'] = '1'
                return app.test_client().post('/api/payments/notify/wechat', data=raw, headers=headers, content_type='application/json')
            values = {'appid': 'test-app', 'mchid': 'test-merchant', 'out_trade_no': number,
                      'trade_state': 'SUCCESS', 'transaction_id': 'wechat-' + suffix, 'amount': {'total': 10000, 'currency': 'CNY'}}
            assert wechat(values, bad_signature=True).status_code == 400
            assert wechat(values, stale=True).status_code == 400
            assert wechat({**values, 'mchid': 'attacker'}).status_code == 400
            assert wechat({**values, 'amount': {'total': 1, 'currency': 'CNY'}}).status_code == 409
            with ThreadPoolExecutor(max_workers=2) as executor:
                assert [value.status_code for value in executor.map(lambda _: wechat(values), range(2))] == [204, 204]
            with app.app_context():
                assert len(Registration.get(wechat_id).transactions) == 1
            assert other.get(f'/api/payments/{wechat_id}/').json['registration_state'] == 'complete'
    assert organizer.post(f'/api/conferences/{event_id}/publication', json={'published': False}, headers=oh).status_code == 200
    assert attendee.get(detail_url).status_code == 403, 'Withdrawal must protect financial pages'
finally:
    get_patch.stop()
    set_patch.stop()
    with app.test_request_context():
        db.session.rollback()
        if event_id:
            event = Event.get(event_id)
            assert event.id not in (22, 61) and event.title.startswith('收费闭环验收 ')
            event.is_deleted = True
        for user_id in users:
            user = User.get(user_id)
            assert user.email.startswith('payments-') and suffix in user.email
            user.is_deleted = True
        db.session.commit()

print(json.dumps({'passed': True, 'native_fee_registration': True, 'approval_before_payment': True,
                  'company_bank_confirmation': True, 'duplicate_payment_protected': True,
                  'invoice_request_recorded': True, 'full_refund_withdraws_registration': True,
                  'private_export': True, 'signed_alipay_callback': True, 'signed_encrypted_wechat_callback': True,
                  'concurrent_callback_idempotency': True, 'mail_backend': 'memory', 'real_money_moved': False}))
