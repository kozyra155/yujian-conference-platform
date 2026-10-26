"""Company collection using native registration amounts and payment transactions."""
import copy
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import request, session
from werkzeug.exceptions import BadRequest, Conflict

from indico.core.db import db
from indico.modules.events.models.settings import EventSetting
from indico.modules.events.payment.models.transactions import PaymentTransaction, TransactionAction
from indico.modules.events.payment.util import register_transaction
from indico.modules.events.payment import payment_event_settings
from indico.modules.events.registration.models.registrations import Registration, RegistrationState
from indico.util.date_time import now_utc

from . import YujianSitePlugin

MODULE = 'yujian_payments'
COMPANY_DEFAULT = {'enabled': False, 'account_name': '', 'bank_name': '', 'account_number': '',
                   'contact': '', 'revision': 0, 'audit': []}


def money(value, *, positive=False):
    if isinstance(value, (bool, dict, list)) or value is None or len(str(value)) > 30:
        raise BadRequest('金额格式不正确 / Invalid amount.')
    try:
        amount = Decimal(str(value))
        if (not amount.is_finite() or amount < 0 or amount > Decimal('999999999.99')
                or amount != amount.quantize(Decimal('.01')) or positive and amount == 0):
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise BadRequest('金额须为有效人民币金额，最多两位小数 / Invalid CNY amount.') from None
    return format(amount, '.2f')


def required(data, name, length=200):
    value = data.get(name)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > length or any(ord(c) < 32 for c in value):
        raise BadRequest(f'{name}: 请填写有效信息 / Required valid text (max {length}).')
    return value.strip()


def total(registration):
    # Native option prices are floats; normalize their computed sum to currency cents.
    return money(registration.price.quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def audit(record, action, **details):
    record.setdefault('audit', []).append({'action': action, 'at': now_utc().isoformat(),
                                           'by': session.user.id if session.user else None, **details})


def company_config():
    return copy.deepcopy(YujianSitePlugin.settings.get('company_payments') or COMPANY_DEFAULT)


def company_ready(config=None):
    config = config if config is not None else company_config()
    return bool(config.get('enabled') and all(config.get(k) for k in ('account_name', 'bank_name', 'account_number', 'contact')))


def company_public():
    config = company_config()
    return {k: config.get(k, '') for k in ('account_name', 'bank_name', 'account_number', 'contact')} if company_ready(config) else None


def save_company(data):
    db.session.execute(db.text('SELECT pg_advisory_xact_lock(12880, 1)'))
    current = company_config()
    if type(data.get('revision')) is not int or data['revision'] != current['revision']:
        raise Conflict('配置已更新，请刷新 / Settings changed. Refresh first.')
    if set(data) - {'enabled', 'revision', 'account_name', 'bank_name', 'account_number', 'contact'} or type(data.get('enabled')) is not bool:
        raise BadRequest('Invalid company collection settings.')
    result = {'enabled': data['enabled'], 'revision': current['revision'] + 1, 'audit': current.get('audit', [])[-49:]}
    for key in ('account_name', 'bank_name', 'account_number', 'contact'):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value) > 200 or any(ord(c) < 32 for c in value):
            raise BadRequest(f'Invalid {key}.')
        result[key] = value.strip()
    if result['enabled'] and not company_ready(result):
        raise BadRequest('启用前请填写完整公司账户 / Complete the company account before enabling.')
    if result['account_number'] and not re.fullmatch(r'[0-9]{6,40}', result['account_number'].replace(' ', '').replace('-', '')):
        raise BadRequest('请核对银行账号 / Invalid bank account number.')
    audit(result, 'company_account_updated')
    YujianSitePlugin.settings.set('company_payments', result)
    return result


def order_row(registration):
    return EventSetting.query.filter_by(event_id=registration.event_id, module=MODULE, name=f'order_{registration.id}').populate_existing().one_or_none()


def get_order(registration):
    row = order_row(registration)
    return copy.deepcopy(row.value) if row else None


def put_order(registration, order):
    row = order_row(registration)
    if row is None:
        row = EventSetting(event_id=registration.event_id, module=MODULE, name=f'order_{registration.id}')
        db.session.add(row)
    row.value = copy.deepcopy(order)
    db.session.flush()


def lock_registration(registration):
    return Registration.query.filter_by(id=registration.id).populate_existing().with_for_update().one()


def check_amount(registration, order):
    if registration.currency != 'CNY' or order['amount'] != total(registration):
        raise Conflict('报名金额已变化，请联系财务核对 / Registration amount changed. Contact finance.')


def ensure_order(registration):
    registration = lock_registration(registration)
    if registration.is_deleted:
        raise Conflict('报名已删除 / Registration was deleted.')
    order = get_order(registration)
    if order:
        return order
    # First-order creation must serialize with native form/event deletion and fee changes.
    from indico.modules.events import Event
    from indico.modules.events.registration.models.forms import RegistrationForm
    form = RegistrationForm.query.filter_by(id=registration.registration_form_id).populate_existing().with_for_update().one()
    event = Event.query.filter_by(id=registration.event_id).populate_existing().with_for_update().one()
    if form.is_deleted or event.is_deleted:
        raise Conflict('会议或报名表已删除 / Event or registration form was deleted.')
    if (registration.state != RegistrationState.unpaid or not registration.event.has_feature('payment')
            or not YujianSitePlugin.event_settings.get(registration.event, 'company_collection', False)):
        raise Conflict('报名审核通过并产生应付费用后才能付款 / Payment is available after approval.')
    if registration.currency != 'CNY':
        raise Conflict('公司收款仅支持人民币 / Company collection requires CNY.')
    conditions = payment_event_settings.get(registration.event, 'conditions') or ''
    if not conditions.strip():
        raise Conflict('请主办方先配置缴费与退款说明 / Ask the organizer to configure payment and refund conditions.')
    order = {'number': 'YJ' + uuid.uuid4().hex[:28], 'registration_id': registration.id,
             'event_id': registration.event_id, 'amount': money(total(registration), positive=True), 'currency': 'CNY',
             'status': 'awaiting', 'created_at': now_utc().isoformat(), 'audit': [],
             'conditions': conditions, 'terms_accepted_at': None,
             'transfer': None, 'payment': None, 'refund': None, 'invoice': None, 'checkout': None}
    audit(order, 'order_created')
    put_order(registration, order)
    return order


def on_registration(registration, **kwargs):
    if (registration.id and registration.state == RegistrationState.unpaid
            and YujianSitePlugin.event_settings.get(registration.event, 'company_collection', False)):
        ensure_order(registration)


def protect_native_financial_changes(sender, rh, **kwargs):
    if request.method != 'POST' or sender.__name__ not in {
            'RHRegistrationManageWithdraw', 'RHRegistrationWithdraw', 'RHRegistrationReset',
            'RHRegistrationsReset', 'RHRegistrationsBasePrice', 'RHRegistrationEdit',
            'RHRegistrationDisplayEdit', 'RHRegistrationScheduleModification'}:
        return
    registrations = ([rh.registration] if getattr(rh, 'registration', None) is not None
                     else getattr(rh, 'registrations', []))
    # Use the checkout/callback lock, in ID order for native bulk operations.
    for registration in sorted(registrations, key=lambda item: item.id):
        registration = lock_registration(registration)
        if get_order(registration):
            raise Conflict('报名已有财务订单，不能在此撤销、重置或修改；请联系公司财务处理。 / '
                           'This registration has a financial order. Contact company finance before changing it.')


def protect_registration(registration, **kwargs):
    if get_order(registration):
        raise Conflict('报名关联财务订单，不能删除；请联系公司财务处理并保留账务 / Preserve registrations with financial orders; contact company finance.')


def protect_form(form, **kwargs):
    ordered = db.session.query(Registration.id).join(EventSetting, db.and_(
        EventSetting.event_id == Registration.event_id, EventSetting.module == MODULE,
        EventSetting.name == db.func.concat('order_', Registration.id))).filter(
        Registration.registration_form_id == form.id).first()
    if form.is_deleted and ordered:
        raise Conflict('报名表关联财务订单，不能删除 / Preserve forms with financial orders.')
    if YujianSitePlugin.event_settings.get(form.event, 'company_collection', False) and form.retention_period is not None:
        raise Conflict('公司收费报名表不能自动清理财务记录 / Automatic purging is disabled for company collection forms.')


def protect_event(event, **kwargs):
    if EventSetting.query.filter_by(event_id=event.id, module=MODULE).first():
        raise Conflict('会议关联财务订单，请保留会议并撤回公开发布 / Preserve financial records; withdraw publication instead.')


def pay_url(registration):
    return f'/payments/{registration.id}/' if YujianSitePlugin.event_settings.get(
        registration.event, 'company_collection', False) and registration.price else None


def serialize_order(registration, order, *, finance=False):
    order = copy.deepcopy(order) if order else None
    result = {'registration_id': registration.id, 'event_id': registration.event_id,
              'event_title': registration.event.title, 'form_title': registration.registration_form.title,
              'registration_state': registration.state.name, 'amount': total(registration),
              'currency': registration.currency, 'url': f'/payments/{registration.id}/',
              'registration_url': f'/event/{registration.event_id}/registrations/{registration.registration_form_id}/',
              'order': order, 'company': company_public(), 'can_pay': False}
    if order:
        result['can_pay'] = (order['status'] in ('awaiting', 'review') and registration.state == RegistrationState.unpaid
                             and order['amount'] == total(registration) and registration.currency == 'CNY'
                             and not registration.event.is_locked and company_ready())
        if not finance:
            order.pop('audit', None)
            order.pop('checkout', None)
    if finance:
        result.update(name=registration.full_name, email=registration.email)
    return result


def transfer(registration, data):
    order = ensure_order(registration)
    order = accept_terms(registration, data)
    check_amount(registration, order)
    if not company_ready() or registration.state != RegistrationState.unpaid or order['status'] not in ('awaiting', 'review'):
        raise Conflict('当前无法提交付款信息 / Payment is unavailable.')
    if order.get('checkout'):
        raise Conflict('已选择在线支付，请先联系财务确认订单 / Online checkout already exists.')
    claim = {key: required(data, key, 120) for key in ('payer', 'reference')}
    if order['transfer'] == claim:
        return order
    order.update(transfer=claim, status='review')
    audit(order, 'transfer_claimed')
    put_order(registration, order)
    return order


def accept_terms(registration, data):
    order = ensure_order(registration)
    if data.get('accepted_terms') is not True or not order.get('conditions', '').strip():
        raise BadRequest('请阅读并同意缴费与退款说明 / Read and accept the payment and refund conditions.')
    if not order.get('terms_accepted_at'):
        order['terms_accepted_at'] = now_utc().isoformat()
        audit(order, 'payment_conditions_accepted')
        put_order(registration, order)
    return order


def confirm_payment(registration, order, reference, provider='bank', *, amount):
    if money(amount, positive=True) != order['amount']:
        raise Conflict('到账金额与订单不一致 / Received amount does not match the order.')
    # Serialize identical bank/gateway references across different conference registrations.
    db.session.execute(db.text('SELECT pg_advisory_xact_lock(12881, hashtext(:reference))'),
                       {'reference': provider + ':' + reference})
    existing = PaymentTransaction.query.filter(PaymentTransaction.data['company_reference'].astext == reference,
                                               PaymentTransaction.data['company_provider'].astext == provider).first()
    if existing and existing.registration_id != registration.id:
        raise Conflict('该流水已用于其他订单 / This transaction reference is already used.')
    duplicate = EventSetting.query.filter(
        EventSetting.module == MODULE, EventSetting.value['payment']['reference'].astext == reference,
        EventSetting.value['payment']['provider'].astext == provider,
        EventSetting.value['registration_id'].astext != str(registration.id)).first()
    if duplicate:
        raise Conflict('该流水已用于其他订单 / This transaction reference is already used.')
    if order['status'] in ('paid', 'refund_requested', 'refunded', 'payment_exception'):
        if order['payment']['reference'] != reference or order['payment']['provider'] != provider:
            raise Conflict('订单已使用其他流水入账 / Order already paid with another reference.')
        return order
    eligible = (registration.currency == 'CNY' and order['amount'] == total(registration)
                and not registration.is_paid and registration.state == RegistrationState.unpaid
                and not registration.is_deleted and order['status'] in ('awaiting', 'review'))
    if not eligible and provider in ('wechat', 'alipay'):
        # Signed provider receipts must survive legacy edits without approving an invalid registration.
        order.update(status='payment_exception', payment={'reference': reference, 'provider': provider,
                     'amount': order['amount'], 'at': now_utc().isoformat()})
        audit(order, 'payment_exception', reference=reference, registration_state=registration.state.name,
              registration_amount=total(registration), registration_currency=registration.currency)
        put_order(registration, order)
        return order
    check_amount(registration, order)
    if not eligible:
        raise Conflict('请先核对报名与付款状态 / Registration cannot be paid in its current state.')
    transaction = register_transaction(registration, Decimal(order['amount']), 'CNY', TransactionAction.complete,
                                       data={'company_order': order['number'], 'company_reference': reference,
                                             'company_provider': provider})
    if not transaction:
        raise Conflict('交易未能入账 / Transaction could not be recorded.')
    order.update(status='paid', payment={'reference': reference, 'provider': provider,
                                        'amount': order['amount'], 'at': now_utc().isoformat()})
    audit(order, 'payment_confirmed', provider=provider, reference=reference)
    put_order(registration, order)
    return order


def apply_refund(registration, data):
    order = get_order(registration)
    if not order or order['status'] not in ('paid', 'refund_requested', 'payment_exception'):
        raise Conflict('仅已付款订单可申请全额退款 / Only paid orders can request a full refund.')
    reason = required(data, 'reason', 500)
    if order['status'] == 'refund_requested':
        return order
    previous_status = order['status']
    order.update(status='refund_requested', refund={'status': 'requested', 'reason': reason, 'previous_status': previous_status,
                 'amount': order['amount'], 'requested_at': now_utc().isoformat()})
    audit(order, 'refund_requested')
    put_order(registration, order)
    return order


def decide_refund(registration, data):
    order = get_order(registration)
    if not order:
        raise Conflict('No order.')
    action = data.get('action')
    if order['status'] == 'refunded' and action == 'confirm':
        if required(data, 'reference', 120) != order['refund']['reference'] or money(data.get('amount'), positive=True) != order['amount']:
            raise Conflict('退款已经使用其他流水登记 / A different completed refund is already recorded.')
        return order
    if order['status'] != 'refund_requested' or action not in ('confirm', 'reject'):
        raise Conflict('无待处理退款 / No pending refund.')
    note = required(data, 'note', 500)
    if action == 'reject':
        order['refund'].update(status='rejected', note=note)
        order['status'] = order['refund'].get('previous_status', 'paid')
        audit(order, 'refund_rejected', note=note)
    else:
        reference = required(data, 'reference', 120)
        if money(data.get('amount'), positive=True) != order['amount']:
            raise Conflict('当前仅支持全额退款 / Only full refunds are supported.')
        exceptional = order['refund'].get('previous_status') == 'payment_exception'
        if not exceptional and not registration.is_paid:
            raise Conflict('原交易状态已变化，请核对 / Original payment state changed.')
        db.session.execute(db.text('SELECT pg_advisory_xact_lock(12882, hashtext(:reference))'), {'reference': reference})
        duplicate = PaymentTransaction.query.filter(PaymentTransaction.data['company_refund_reference'].astext == reference).first()
        recorded = EventSetting.query.filter(EventSetting.module == MODULE,
                   EventSetting.value['refund']['reference'].astext == reference).first()
        if duplicate or recorded:
            raise Conflict('退款流水已使用 / Refund reference already used.')
        if not exceptional:
            transaction = register_transaction(registration, Decimal(order['amount']), 'CNY', TransactionAction.cancel,
                                               data={'company_order': order['number'], 'company_refund_reference': reference})
            if not transaction:
                raise Conflict('Refund could not be recorded.')
        registration.update_state(withdrawn=True)
        order['refund'].update(status='refunded', reference=reference, note=note, at=now_utc().isoformat())
        order['status'] = 'refunded'
        audit(order, 'refund_confirmed', reference=reference, note=note)
    put_order(registration, order)
    return order


def apply_invoice(registration, data):
    order = get_order(registration)
    if not order or order['status'] != 'paid':
        raise Conflict('仅已付款且未申请退款的订单可申请开票 / Invoice requests require a paid order.')
    if order.get('invoice') and order['invoice']['status'] == 'issued':
        raise Conflict('发票已开具，请联系财务 / Invoice already issued.')
    kind = data.get('kind')
    if kind not in ('personal', 'company'):
        raise BadRequest('Invalid invoice kind.')
    email = required(data, 'email', 254)
    from email_validator import validate_email, EmailNotValidError
    try:
        email = validate_email(email, check_deliverability=False).email
    except EmailNotValidError:
        raise BadRequest('请填写有效邮箱 / Invalid email.') from None
    tax_id = required(data, 'tax_id', 30).upper() if kind == 'company' else ''
    if tax_id and not re.fullmatch(r'[0-9A-Z]{15,20}', tax_id):
        raise BadRequest('请核对税号 / Invalid tax ID.')
    order['invoice'] = {'kind': kind, 'title': required(data, 'title', 200), 'tax_id': tax_id,
                        'email': email, 'status': 'requested', 'requested_at': now_utc().isoformat()}
    audit(order, 'invoice_requested')
    put_order(registration, order)
    return order


def issue_invoice(registration, data):
    order = get_order(registration)
    if not order or order['status'] != 'paid' or not order.get('invoice'):
        raise Conflict('无可处理开票申请 / No eligible invoice request.')
    number = required(data, 'number', 100)
    if order['invoice']['status'] == 'issued':
        if order['invoice']['number'] != number:
            raise Conflict('已登记不同发票号 / A different invoice is already recorded.')
        return order
    order['invoice'].update(status='issued', number=number, at=now_utc().isoformat())
    audit(order, 'invoice_issued', number=number)
    put_order(registration, order)
    return order
