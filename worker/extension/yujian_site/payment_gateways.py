"""Optional company-owned WeChat Native and Alipay page payment, closed until configured."""
import base64
import io
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

import qrcode
import requests
from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from flask import request
from werkzeug.exceptions import BadRequest, Conflict, ServiceUnavailable

from indico.core.config import config
from indico.core.db import db
from indico.modules.events.models.settings import EventSetting
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.util.date_time import now_utc

from . import payments as p


def merchant_config():
    path = Path(os.environ.get('YUJIAN_PAYMENT_CONFIG', '/opt/indico/etc/payment-config/merchant.json'))
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def key(path, *, private=False):
    raw = Path(path).read_bytes()
    result = serialization.load_pem_private_key(raw, password=None) if private else serialization.load_pem_public_key(raw)
    if not isinstance(result, rsa.RSAPrivateKey if private else rsa.RSAPublicKey) or result.key_size < 2048:
        raise ValueError('RSA 2048 or stronger required.')
    return result


def gateway_config(provider, *, callback=False):
    if provider not in ('wechat', 'alipay'):
        raise BadRequest('Invalid payment provider.')
    settings = merchant_config().get(provider, {})
    try:
        if not isinstance(settings, dict) or (not callback and settings.get('enabled') is not True):
            raise ValueError()
        fields = (('appid', 'mchid', 'serial_no', 'platform_key_id', 'api_v3_key', 'platform_public_key_path')
                  if provider == 'wechat' else ('app_id', 'seller_id', 'alipay_public_key_path'))
        if not all(isinstance(settings.get(name), str) and settings[name].strip() for name in fields):
            raise ValueError()
        key(settings['private_key_path'], private=True)
        key(settings['platform_public_key_path'] if provider == 'wechat' else settings['alipay_public_key_path'])
        if provider == 'wechat' and len(settings['api_v3_key'].encode()) != 32:
            raise ValueError()
        if not callback:
            base = urlsplit(config.BASE_URL)
            if base.scheme != 'https' or not base.hostname or base.hostname in ('localhost', '127.0.0.1') or not p.company_ready():
                raise ValueError()
        return settings
    except (KeyError, TypeError, ValueError, OSError):
        raise ServiceUnavailable('支付通道尚未配置完成 / Payment channel is not configured.') from None


def available_gateways():
    result = {}
    for provider in ('wechat', 'alipay'):
        try:
            gateway_config(provider)
            result[provider] = True
        except ServiceUnavailable:
            result[provider] = False
    return result


def sign(data, settings):
    signature = key(settings['private_key_path'], private=True).sign(data.encode(), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()


def verify(data, signature, public_key_path):
    try:
        key(public_key_path).verify(base64.b64decode(signature, validate=True), data.encode(), padding.PKCS1v15(), hashes.SHA256())
    except (ValueError, TypeError, InvalidSignature, OSError):
        raise BadRequest('Invalid payment signature.') from None


def wechat_verify(headers, raw, settings):
    try:
        timestamp, nonce = headers['Wechatpay-Timestamp'], headers['Wechatpay-Nonce']
        if abs(time.time() - int(timestamp)) > 300 or headers['Wechatpay-Serial'] != settings['platform_key_id']:
            raise ValueError()
        verify(f'{timestamp}\n{nonce}\n{raw}\n', headers['Wechatpay-Signature'], settings['platform_public_key_path'])
    except (KeyError, ValueError, TypeError):
        raise BadRequest('Invalid WeChat notification headers.') from None


def wechat_request(path, payload, settings, *, method='POST'):
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')) if payload is not None else ''
    nonce, timestamp = uuid.uuid4().hex, str(int(time.time()))
    signature = sign(f'{method}\n{path}\n{timestamp}\n{nonce}\n{raw}\n', settings)
    authorization = (f'WECHATPAY2-SHA256-RSA2048 mchid="{settings["mchid"]}",nonce_str="{nonce}",'
                     f'timestamp="{timestamp}",serial_no="{settings["serial_no"]}",signature="{signature}"')
    try:
        send = requests.get if method == 'GET' else requests.post
        result = send('https://api.mch.weixin.qq.com' + path, **({'data': raw.encode()} if raw else {}),
                               headers={'Authorization': authorization, 'Content-Type': 'application/json',
                                        'Accept': 'application/json', 'Wechatpay-Serial': settings['platform_key_id']},
                               timeout=(5, 15), allow_redirects=False)
        if result.status_code == 204 and path.endswith('/close'):
            return {}
        wechat_verify(result.headers, result.text, settings)
        if result.status_code != 200:
            raise ValueError()
        return result.json()
    except (requests.RequestException, ValueError, BadRequest):
        raise ServiceUnavailable('未能取得支付信息，请重试或联系财务 / Checkout is unavailable. Retry or contact finance.') from None


def alipay_request(method, number, settings):
    params = {'app_id': settings['app_id'], 'method': method, 'format': 'JSON', 'charset': 'utf-8',
              'sign_type': 'RSA2', 'version': '1.0', 'timestamp': now_utc().astimezone(
                  ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'),
              'biz_content': json.dumps({'out_trade_no': number}, separators=(',', ':'))}
    params['sign'] = sign('&'.join(f'{k}={v}' for k, v in sorted(params.items())), settings)
    try:
        result = requests.post('https://openapi.alipay.com/gateway.do', data=params,
                               timeout=(5, 15), allow_redirects=False)
        if result.status_code != 200:
            raise ValueError()
        name = method.replace('.', '_') + '_response'
        match = re.search(r'"' + name + r'"\s*:\s*', result.text)
        if not match:
            raise ValueError()
        fields, size = json.JSONDecoder().raw_decode(result.text[match.end():])
        verify(result.text[match.end():match.end()+size], result.json().get('sign', ''), settings['alipay_public_key_path'])
        if not isinstance(fields, dict):
            raise ValueError()
        return fields
    except (requests.RequestException, ValueError, BadRequest):
        raise ServiceUnavailable('无法核对支付宝订单，请稍后重试 / Unable to verify the Alipay order. Retry later.') from None


def checkout_expired(checkout):
    try:
        return now_utc() >= datetime.fromisoformat(checkout['expires_at'])
    except (KeyError, ValueError, TypeError):
        return True  # Legacy links must be queried before they can be reissued.


def reconcile_checkout(registration, order, settings):
    """Return a safe merchant number to retry, or None if the old transaction was paid."""
    checkout = order['checkout']
    provider, number = checkout['provider'], checkout.get('number', order['number'])
    if provider == 'wechat':
        path = f'/v3/pay/transactions/out-trade-no/{number}'
        fields = wechat_request(path + '?' + urlencode({'mchid': settings['mchid']}), None, settings, method='GET')
        if (fields.get('appid') != settings['appid'] or fields.get('mchid') != settings['mchid']
                or fields.get('out_trade_no') != number):
            raise ServiceUnavailable('WeChat order mismatch.')
        state = fields.get('trade_state')
        if state == 'SUCCESS':
            amount = fields.get('amount', {})
            if amount.get('currency') != 'CNY' or type(amount.get('total')) is not int:
                raise ServiceUnavailable('WeChat amount mismatch.')
            reference, received = fields.get('transaction_id'), Decimal(amount['total']) / 100
        elif state in ('NOTPAY', 'CLOSED'):
            if state == 'NOTPAY':
                wechat_request(path + '/close', {'mchid': settings['mchid']}, settings)
            return 'YJ' + uuid.uuid4().hex[:28]
        else:
            raise ServiceUnavailable('支付状态尚未确认，请稍后重试 / Payment state is uncertain. Retry later.')
    else:
        fields = alipay_request('alipay.trade.query', number, settings)
        if fields.get('code') == '40004' and fields.get('sub_code') == 'ACQ.TRADE_NOT_EXIST':
            # An unopened legacy URL can still create a trade; reuse its number to prevent two payable trades.
            return number
        if fields.get('code') != '10000' or fields.get('out_trade_no') != number:
            raise ServiceUnavailable('Alipay order query failed.')
        state = fields.get('trade_status')
        if state in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
            reference, received = fields.get('trade_no'), fields.get('total_amount')
        elif state in ('WAIT_BUYER_PAY', 'TRADE_CLOSED'):
            if state == 'WAIT_BUYER_PAY':
                closed = alipay_request('alipay.trade.close', number, settings)
                if closed.get('code') != '10000' or closed.get('out_trade_no') != number:
                    raise ServiceUnavailable('Alipay order close failed. Retry to verify its final state.')
            return 'YJ' + uuid.uuid4().hex[:28]
        else:
            raise ServiceUnavailable('支付宝交易状态尚未确认 / Alipay trade state is uncertain.')
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 120:
        raise ServiceUnavailable('Invalid provider transaction reference.')
    p.confirm_payment(registration, order, reference, provider, amount=received)
    return None


def checkout_public(checkout):
    if not checkout:
        return None
    if checkout['provider'] == 'alipay':
        return {'provider': 'alipay', 'url': checkout['url'], 'expired': checkout_expired(checkout)}
    buffer = io.BytesIO()
    qrcode.make(checkout['code_url']).save(buffer, format='PNG')
    return {'provider': 'wechat', 'qr': 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode(),
            'expires_at': checkout['expires_at'], 'expired': checkout_expired(checkout)}


def start_checkout(registration, provider):
    settings = gateway_config(provider)
    order = p.ensure_order(registration)
    p.check_amount(registration, order)
    if order['status'] != 'awaiting' or registration.state != RegistrationState.unpaid:
        raise Conflict('当前订单无法发起支付 / This order cannot start checkout.')
    number = order['number']
    if order.get('checkout'):
        if order['checkout']['provider'] != provider:
            raise Conflict('订单已选择其他支付方式，请联系财务 / This order already uses a different payment channel.')
        if not checkout_expired(order['checkout']):
            return checkout_public(order['checkout'])
        number = reconcile_checkout(registration, order, settings)
        if number is None:
            return {'paid': True}
        p.audit(order, 'checkout_closed', provider=provider, number=order['checkout'].get('number', order['number']))
    expires = now_utc() + timedelta(hours=2)
    notify_url = config.BASE_URL.rstrip('/') + f'/api/payments/notify/{provider}'
    if provider == 'alipay':
        params = {'app_id': settings['app_id'], 'method': 'alipay.trade.page.pay', 'format': 'JSON',
                  'charset': 'utf-8', 'sign_type': 'RSA2', 'timestamp': now_utc().astimezone(
                      ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S'),
                  'version': '1.0', 'notify_url': notify_url,
                  'return_url': config.BASE_URL.rstrip('/') + f'/payments/{registration.id}/',
                  'biz_content': json.dumps({'out_trade_no': number, 'product_code': 'FAST_INSTANT_TRADE_PAY',
                                            'total_amount': order['amount'], 'subject': registration.event.title[:100],
                                            'seller_id': settings['seller_id'], 'timeout_express': '2h',
                                            'time_expire': expires.astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S')},
                                           ensure_ascii=False, separators=(',', ':'))}
        params['sign'] = sign('&'.join(f'{k}={v}' for k, v in sorted(params.items()) if v != ''), settings)
        checkout = {'provider': provider, 'url': 'https://openapi.alipay.com/gateway.do?' + urlencode(params)}
    else:
        result = wechat_request('/v3/pay/transactions/native', {
            'appid': settings['appid'], 'mchid': settings['mchid'], 'description': registration.event.title[:40],
            'out_trade_no': number, 'time_expire': expires.isoformat(), 'notify_url': notify_url,
            'amount': {'total': int(Decimal(order['amount']) * 100), 'currency': 'CNY'}}, settings)
        code = result.get('code_url')
        if not isinstance(code, str) or not code.startswith('weixin://wxpay/bizpayurl?') and not code.startswith('weixin://pay.weixin.qq.com/'):
            raise ServiceUnavailable('Invalid WeChat checkout response.')
        checkout = {'provider': provider, 'code_url': code}
    checkout.update(number=number, expires_at=expires.isoformat())
    order['checkout'] = checkout
    p.audit(order, 'checkout_created', provider=provider)
    p.put_order(registration, order)
    return checkout_public(checkout)


def process_notification(provider):
    settings = gateway_config(provider, callback=True)
    if request.content_length and request.content_length > 65536:
        raise BadRequest('Notification too large.')
    if provider == 'alipay':
        if any(len(values) != 1 for _, values in request.form.lists()):
            raise BadRequest('Duplicate notification fields.')
        fields = request.form.to_dict()
        if fields.get('sign_type') != 'RSA2':
            raise BadRequest('RSA2 required.')
        verify('&'.join(f'{k}={v}' for k, v in sorted(fields.items()) if k not in ('sign', 'sign_type') and v != ''),
               fields.get('sign', ''), settings['alipay_public_key_path'])
        if fields.get('app_id') != settings['app_id'] or fields.get('seller_id') != settings['seller_id']:
            raise BadRequest('Payment merchant mismatch.')
        if fields.get('trade_status') not in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
            return
        number, reference, amount = fields.get('out_trade_no'), fields.get('trade_no'), fields.get('total_amount')
    else:
        raw = request.get_data(as_text=True)
        wechat_verify(request.headers, raw, settings)
        try:
            envelope = json.loads(raw)
            if envelope.get('event_type') != 'TRANSACTION.SUCCESS':
                raise ValueError()
            resource = envelope['resource']
            if resource['algorithm'] != 'AEAD_AES_256_GCM':
                raise ValueError()
            fields = json.loads(AESGCM(settings['api_v3_key'].encode()).decrypt(resource['nonce'].encode(),
                                base64.b64decode(resource['ciphertext'], validate=True), resource.get('associated_data', '').encode()))
            if (fields['appid'] != settings['appid'] or fields['mchid'] != settings['mchid']
                    or fields['trade_state'] != 'SUCCESS' or fields['amount']['currency'] != 'CNY'
                    or type(fields['amount']['total']) is not int):
                raise ValueError()
            number, reference = fields['out_trade_no'], fields['transaction_id']
            amount = Decimal(fields['amount']['total']) / 100
        except (KeyError, TypeError, ValueError, InvalidTag):
            raise BadRequest('Invalid WeChat payment notification.') from None
    if not isinstance(number, str) or not re.fullmatch(r'YJ[0-9a-f]{28}', number):
        raise BadRequest('Invalid order number.')
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 120:
        raise BadRequest('Invalid transaction reference.')
    row = EventSetting.query.filter(EventSetting.module == p.MODULE, db.or_(
        EventSetting.value['number'].astext == number,
        EventSetting.value['checkout']['number'].astext == number)).one_or_none()
    if row is None:
        raise BadRequest('Unknown company order.')
    registration = Registration.get(row.value['registration_id'])
    registration = p.lock_registration(registration)
    order = p.get_order(registration)
    if (not order.get('checkout') or order['checkout']['provider'] != provider
            or order['checkout'].get('number', order['number']) != number):
        raise BadRequest('Payment channel mismatch.')
    p.confirm_payment(registration, order, reference, provider, amount=amount)
