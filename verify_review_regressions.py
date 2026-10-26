"""Review regressions: disposable records, memory mail, no payment network access."""
import copy
import json
import os
import tempfile
import unittest
import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

os.environ['PYTEST_CURRENT_TEST'] = 'verify_review_regressions'
from flask import session
from indico.core.db import db
from indico.modules.auth import Identity
from indico.modules.events import Event
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.payment import payment_event_settings
from indico.modules.events.registration.models.forms import RegistrationForm
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.modules.events.registration.util import create_personal_data_fields
from indico.modules.users import User
from indico.modules.users.operations import create_user
from indico.util.date_time import now_utc
from indico.web.flask.app import make_app
from yujian_site import YujianSitePlugin, payments as p, payment_gateways as gateway

app = make_app(config_override={'EMAIL_BACKEND': 'indico.vendor.django_mail.backends.locmem.EmailBackend',
                                'SMTP_USE_CELERY': False})
app.config.update(TESTING=True, REPL=True)


class ReviewRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suffix = uuid.uuid4().hex[:10]
        cls.events = []
        with app.test_request_context():
            user = create_user(f'review-{cls.suffix}@conference.test',
                               {'first_name': 'Review', 'last_name': cls.suffix},
                               Identity(provider='indico', identifier='review-' + cls.suffix, password=uuid.uuid4().hex))
            user.is_admin = True
            db.session.commit()
            cls.user_id = user.id

    @classmethod
    def tearDownClass(cls):
        with app.test_request_context():
            db.session.rollback()
            for event_id in cls.events:
                event = Event.get(event_id)
                assert event_id not in (22, 61, 171) and cls.suffix in event.title
                event.is_deleted = True
            User.get(cls.user_id).is_deleted = True
            db.session.commit()

    def setUp(self):
        self.network = []
        for method in ('get', 'post'):
            mock = patch.object(gateway.requests, method, side_effect=AssertionError('Real payment HTTP prohibited'))
            self.network.append(mock.start())
            self.addCleanup(mock.stop)
        for name, value in [('company_ready', True), ('company_public', {'contact': 'TEST ONLY'})]:
            mock = patch.object(p, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        self.client = app.test_client()
        with app.test_request_context(), self.client.session_transaction() as saved:
            saved.set_session_user(User.get(self.user_id))
        self.headers = {'X-CSRF-Token': json.loads(self.client.get('/assets/js-vars/user.js?portal=1').data)['csrf_token']}
        result = self.client.post('/api/conferences/', json={
            'title': f'Review disposable {self.suffix}', 'start': '2027-10-20T09:00', 'end': '2027-10-22T17:00',
            'location': 'Test', 'description': 'Disposable regression fixture', 'template': 'academic-full',
            'organizer_name': 'Fixture', 'organizer_phone': '123456', 'country': '中国',
            'province': '湖北省', 'city': '武汉市', 'detail_address': 'Fixture address'}, headers=self.headers)
        self.assertEqual(result.status_code, 201)
        self.event_id = result.json['id']
        self.events.append(self.event_id)
        with app.test_request_context():
            event = Event.get(self.event_id)
            YujianSitePlugin.event_settings.set(event, 'company_collection', True)
            set_feature_enabled(event, 'payment', True)
            payment_event_settings.set(event, 'conditions', 'TEST ONLY: full refunds by finance')
            form = RegistrationForm(event=event, title='Regression ticket', currency='CNY', base_price=100,
                                    start_dt=now_utc()-timedelta(days=1), end_dt=now_utc()+timedelta(days=2),
                                    require_login=True, require_captcha=False,
                                    notification_sender_address='no-reply@example.invalid')
            create_personal_data_fields(form)
            db.session.add(form)
            db.session.commit()
            self.form_id = form.id
        result = self.client.post(f'/event/{self.event_id}/registrations/{self.form_id}/', json={
            'first_name': 'Review', 'last_name': self.suffix, 'email': f'review-{self.suffix}@conference.test'}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        with app.test_request_context():
            registration = Registration.query.filter_by(registration_form_id=self.form_id, user_id=self.user_id).one()
            self.registration_id = registration.id
        self.url = f'/api/payments/{self.registration_id}/'

    def save_checkout(self, provider='wechat', expired=True):
        with app.test_request_context():
            registration = Registration.get(self.registration_id)
            order = p.get_order(registration)
            order['checkout'] = {'provider': provider, 'number': order['number'],
                'expires_at': (now_utc()+timedelta(hours=-1 if expired else 1)).isoformat(),
                'code_url': 'weixin://wxpay/bizpayurl?pr=OLD', 'url': 'https://openapi.alipay.com/gateway.do?OLD'}
            p.put_order(registration, order)
            db.session.commit()
            return copy.deepcopy(order)

    def test_unedited_dates_preserve_seconds(self):
        with app.test_request_context():
            event = Event.get(self.event_id)
            event.start_dt = event.start_dt.replace(second=30)
            event.end_dt = event.end_dt.replace(second=45)
            db.session.commit()
        url = f'/api/conferences/{self.event_id}/basic'
        result = self.client.get(url).json
        result['basic']['title'] += ' title only'
        result = self.client.put(url, json={k: result[k] for k in ('revision', 'fingerprint', 'basic')}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        with app.test_request_context():
            event = Event.get(self.event_id)
            self.assertEqual((event.start_dt.second, event.end_dt.second), (30, 45))

    def test_native_changes_blocked_for_financial_order(self):
        self.save_checkout()
        prefix = f'/event/{self.event_id}/manage/registration/{self.form_id}/registrations'
        for url, data in [(f'{prefix}/{self.registration_id}/withdraw', {}),
                          (f'{prefix}/{self.registration_id}/reset', {}),
                          (prefix+'/update-price', {'registration_id': [self.registration_id], 'action': 'custom', 'base_price': '200'}),
                          (prefix+'/reset', {'registration_id': [self.registration_id]})]:
            with self.subTest(url=url):
                response = self.client.post(url, data=data, headers=self.headers)
                self.assertEqual(response.status_code, 409)
        with app.test_request_context():
            registration = Registration.get(self.registration_id)
            self.assertEqual(registration.state, RegistrationState.unpaid)
            self.assertEqual(p.total(registration), '100.00')

    def test_expired_wechat_is_closed_before_new_checkout(self):
        old = self.save_checkout()
        calls = []
        def transport(path, payload, settings, **kwargs):
            calls.append((path, kwargs.get('method', 'POST')))
            if kwargs.get('method') == 'GET':
                return {'appid': 'app', 'mchid': 'merchant', 'out_trade_no': old['number'], 'trade_state': 'NOTPAY'}
            if path.endswith('/close'):
                return {}
            self.assertNotEqual(payload['out_trade_no'], old['number'])
            return {'code_url': 'weixin://wxpay/bizpayurl?pr=NEW'}
        with patch.object(gateway, 'gateway_config', return_value={'appid': 'app', 'mchid': 'merchant'}), \
             patch.object(gateway, 'wechat_request', side_effect=transport):
            def start(_):
                client = app.test_client()
                client._cookies = copy.deepcopy(self.client._cookies)
                return client.post(self.url+'checkout', json={'provider': 'wechat', 'accepted_terms': True}, headers=self.headers)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(start, range(2)))
        self.assertEqual([result.status_code for result in results], [200, 200])
        self.assertEqual(len(calls), 3, 'Must query, close, then create')
        with app.test_request_context():
            saved = p.get_order(Registration.get(self.registration_id))
            self.assertEqual(saved['number'], old['number'], 'Company order number stays stable')
            self.assertNotEqual(saved['checkout']['number'], old['number'])

    def test_query_failure_keeps_original_checkout(self):
        old = self.save_checkout()
        from werkzeug.exceptions import ServiceUnavailable
        with patch.object(gateway, 'gateway_config', return_value={'mchid': 'merchant'}), \
             patch.object(gateway, 'wechat_request', side_effect=ServiceUnavailable('Transport uncertain')):
            result = self.client.post(self.url+'checkout', json={'provider': 'wechat', 'accepted_terms': True}, headers=self.headers)
        self.assertEqual(result.status_code, 503)
        with app.test_request_context():
            saved = p.get_order(Registration.get(self.registration_id))
            self.assertEqual(saved['checkout'], old['checkout'])

    def test_paid_query_records_receipt_instead_of_reissuing(self):
        old = self.save_checkout()
        with patch.object(gateway, 'gateway_config', return_value={'appid': 'app', 'mchid': 'merchant'}), \
             patch.object(gateway, 'wechat_request', return_value={
                 'appid': 'app', 'mchid': 'merchant', 'out_trade_no': old['number'], 'trade_state': 'SUCCESS',
                 'transaction_id': 'query-paid-'+self.suffix,
                 'amount': {'total': 10000, 'currency': 'CNY'}}) as transport:
            result = self.client.post(self.url+'checkout', json={'provider': 'wechat', 'accepted_terms': True}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(transport.call_count, 1)
        self.assertEqual(self.client.get(self.url).json['order']['status'], 'paid')

    def test_alipay_unopened_legacy_link_reuses_merchant_number(self):
        old = self.save_checkout('alipay')
        settings = {'app_id': 'app', 'seller_id': 'seller'}
        with patch.object(gateway, 'gateway_config', return_value=settings), \
             patch.object(gateway, 'sign', return_value='test-signature'), \
             patch.object(gateway, 'alipay_request', create=True, return_value={
                 'code': '40004', 'sub_code': 'ACQ.TRADE_NOT_EXIST'}):
            result = self.client.post(self.url+'checkout', json={'provider': 'alipay', 'accepted_terms': True}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        from urllib.parse import parse_qs, urlsplit
        business = json.loads(parse_qs(urlsplit(result.json['url']).query)['biz_content'][0])
        self.assertEqual(business['out_trade_no'], old['number'])
        self.assertIn('time_expire', business, 'New Alipay URLs have an absolute deadline')

    def test_alipay_waiting_trade_is_closed_before_renewal(self):
        old = self.save_checkout('alipay')
        def transport(method, number, settings):
            self.assertEqual(number, old['number'])
            return {'code': '10000', 'out_trade_no': number, 'trade_status': 'WAIT_BUYER_PAY'}
        with patch.object(gateway, 'gateway_config', return_value={'app_id': 'app', 'seller_id': 'seller'}), \
             patch.object(gateway, 'sign', return_value='test-signature'), \
             patch.object(gateway, 'alipay_request', create=True, side_effect=transport) as send:
            result = self.client.post(self.url+'checkout', json={'provider': 'alipay', 'accepted_terms': True}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual([c.args[0] for c in send.call_args_list], ['alipay.trade.query', 'alipay.trade.close'])
        with app.test_request_context():
            self.assertNotEqual(p.get_order(Registration.get(self.registration_id))['checkout']['number'], old['number'])

    def test_alipay_close_race_preserves_old_checkout(self):
        old = self.save_checkout('alipay')
        with patch.object(gateway, 'gateway_config', return_value={}), \
             patch.object(gateway, 'alipay_request', side_effect=[
                 {'code': '10000', 'out_trade_no': old['number'], 'trade_status': 'WAIT_BUYER_PAY'},
                 {'code': '40004', 'sub_code': 'ACQ.TRADE_HAS_SUCCESS'}]):
            result = self.client.post(self.url+'checkout', json={'provider': 'alipay', 'accepted_terms': True}, headers=self.headers)
        self.assertEqual(result.status_code, 503)
        with app.test_request_context():
            self.assertEqual(p.get_order(Registration.get(self.registration_id))['checkout'], old['checkout'])

    def test_signed_gateway_query_transports(self):
        import base64
        import re
        import time
        from pathlib import Path
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from werkzeug.exceptions import ServiceUnavailable
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        def signed(value):
            return base64.b64encode(private.sign(value.encode(), padding.PKCS1v15(), hashes.SHA256())).decode()
        with tempfile.TemporaryDirectory() as directory:
            public_path, private_path = Path(directory)/'public.pem', Path(directory)/'private.pem'
            public_path.write_bytes(private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
            private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            settings = {'app_id': 'app', 'private_key_path': str(private_path), 'alipay_public_key_path': str(public_path),
                        'mchid': 'merchant', 'serial_no': 'merchant-serial', 'platform_key_id': 'platform',
                        'platform_public_key_path': str(public_path)}
            fields = {'code': '10000', 'out_trade_no': 'YJ'+'0'*28, 'trade_status': 'TRADE_CLOSED'}
            raw = json.dumps(fields)
            response = json.dumps({'alipay_trade_query_response': fields, 'sign': signed(raw)})
            with patch.object(gateway.requests, 'post', return_value=SimpleNamespace(
                    status_code=200, text=response, json=lambda:json.loads(response))):
                self.assertEqual(gateway.alipay_request('alipay.trade.query', fields['out_trade_no'], settings), fields)
            tampered = response.replace('TRADE_CLOSED', 'TRADE_SUCCESS')
            with patch.object(gateway.requests, 'post', return_value=SimpleNamespace(
                    status_code=200, text=tampered, json=lambda:json.loads(tampered))):
                with self.assertRaises(ServiceUnavailable):
                    gateway.alipay_request('alipay.trade.query', fields['out_trade_no'], settings)
            def get(url, **options):
                auth = dict(re.findall(r'(\w+)="([^"]*)"', options['headers']['Authorization']))
                path = url.removeprefix('https://api.mch.weixin.qq.com')
                private.public_key().verify(base64.b64decode(auth['signature']),
                    f"GET\n{path}\n{auth['timestamp']}\n{auth['nonce_str']}\n\n".encode(), padding.PKCS1v15(), hashes.SHA256())
                payload = json.dumps({'trade_state': 'CLOSED'})
                timestamp, nonce = str(int(time.time())), 'test-nonce'
                headers = {'Wechatpay-Timestamp': timestamp, 'Wechatpay-Nonce': nonce, 'Wechatpay-Serial': 'platform',
                           'Wechatpay-Signature': signed(f'{timestamp}\n{nonce}\n{payload}\n')}
                return SimpleNamespace(status_code=200, text=payload, headers=headers, json=lambda:json.loads(payload))
            with patch.object(gateway.requests, 'get', side_effect=get):
                self.assertEqual(gateway.wechat_request('/v3/pay/transactions/out-trade-no/TEST?mchid=merchant',
                                                       None, settings, method='GET'), {'trade_state': 'CLOSED'})

    def test_unexpected_paid_notification_is_retained_and_refundable(self):
        self.save_checkout()
        with app.test_request_context():
            registration = Registration.get(self.registration_id)
            registration.base_price = 200  # Legacy/out-of-band edit, not an allowed native action.
            order = p.get_order(registration)
            reference = 'exception-'+self.suffix
            p.confirm_payment(registration, order, reference, 'wechat', amount='100.00')
            db.session.commit()
            saved = p.get_order(registration)
            self.assertEqual(saved['status'], 'payment_exception')
            self.assertEqual(saved['payment']['reference'], reference)
            self.assertEqual(registration.state, RegistrationState.unpaid)
            p.confirm_payment(registration, saved, reference, 'wechat', amount='100.00')
            db.session.commit()
            self.assertEqual(len([a for a in p.get_order(registration)['audit'] if a['action']=='payment_exception']), 1)
        result = self.client.post(self.url+'refund', json={'reason': 'Refund mismatched receipt'}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        result = self.client.post(self.url+'refund-decision', json={
            'action': 'confirm', 'amount': '100.00', 'reference': 'exception-refund-'+self.suffix,
            'note': 'Test only, no real refund'}, headers=self.headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['order']['status'], 'refunded')


if __name__ == '__main__':
    unittest.main(verbosity=2)
