"""Account-owned checkout and company-administrator financial operations."""
import csv
import io

from flask import make_response, request, session
from flask_pluginengine import render_plugin_template
from werkzeug.exceptions import BadRequest, Conflict, Forbidden, NotFound

from indico.core.db import db
from indico.modules.events.features.util import set_feature_enabled
from indico.modules.events.models.settings import EventSetting
from indico.modules.events.payment import payment_settings, payment_event_settings
from indico.modules.events.registration.models.forms import RegistrationForm, ModificationMode
from indico.modules.events.registration.models.registrations import Registration
from indico.modules.events.util import check_event_locked
from indico.web.rh import RH

from . import YujianSitePlugin
from .blueprint import RHAccount, RHManaged, body, response
from .business import event_visible
from . import payments as p


class RHFinance(RHAccount):
    def _check_access(self):
        super()._check_access()
        if not session.user.is_admin:
            raise Forbidden()


class RHCompanyPage(RHFinance):
    def _process(self):
        return render_plugin_template('builder.html', mode='company-payments', event=None)


class RHCompanySettings(RHFinance):
    def _process(self):
        from .payment_gateways import available_gateways
        data = p.save_company(body()) if request.method == 'PUT' else p.company_config()
        return response({'company': data, 'gateways': available_gateways()})


class RHFeesPage(RHManaged):
    def _process(self):
        return render_plugin_template('builder.html', mode='payments', event=self.event)


class RHFees(RHManaged):
    def _process(self):
        if request.method == 'PUT':
            data = body()
            if set(data) - {'form_id', 'base_price', 'conditions'} or not {'form_id', 'base_price'} <= set(data) or type(data['form_id']) is not int:
                raise BadRequest('Expected form_id and base_price.')
            # Serialize fee edits with native registrations without ever altering old registration prices.
            form = RegistrationForm.query.filter_by(id=data['form_id'], event_id=self.event.id,
                                                     is_deleted=False).with_for_update().one_or_none()
            if not form:
                raise NotFound()
            price = p.money(data['base_price'])
            conditions = data.get('conditions', payment_event_settings.get(self.event, 'conditions') or '')
            if not isinstance(conditions, str) or len(conditions) > 4000 or not conditions.strip():
                raise BadRequest('收费前请填写缴费与退款说明 / Add payment and refund conditions before charging.')
            if price != '0.00' and not p.company_ready():
                raise Conflict('请先由平台管理员配置公司收款账户 / Company collection is not configured.')
            if Registration.query.filter_by(registration_form_id=form.id, is_deleted=False).count() and form.currency != 'CNY':
                raise Conflict('已有其他币种报名，请新建人民币报名表 / Create a new CNY form.')
            currencies = payment_settings.get('currencies')
            if not any(item['code'] == 'CNY' for item in currencies):
                payment_settings.set('currencies', currencies + [{'code': 'CNY', 'name': '人民币 / Chinese yuan'}])
            form.currency, form.base_price = 'CNY', price
            form.modification_mode = ModificationMode.not_allowed
            form.retention_period = None
            form.require_login = True
            set_feature_enabled(self.event, 'payment', True)
            YujianSitePlugin.event_settings.set(self.event, 'company_collection', True)
            payment_event_settings.set(self.event, 'conditions', conditions.strip())
        forms = RegistrationForm.query.filter_by(event_id=self.event.id, is_deleted=False).order_by(RegistrationForm.id)
        return response({'event': {'id': self.event.id, 'title': self.event.title, 'locked': self.event.is_locked},
                         'company_ready': p.company_ready(), 'can_confirm': session.user.is_admin,
                         'conditions': payment_event_settings.get(self.event, 'conditions') or '',
                         'forms': [{'id': form.id, 'title': form.title, 'base_price': p.money(form.base_price),
                                    'currency': form.currency, 'url': f'/event/{self.event.id}/manage/registration/{form.id}/'}
                                   for form in forms]})


class RHOrders(RHManaged):
    def _process(self):
        try:
            page = int(request.args.get('page', '1'))
            if not 1 <= page <= 100000:
                raise ValueError()
        except ValueError:
            raise BadRequest('Invalid page.') from None
        query = (Registration.query.join(EventSetting, db.and_(EventSetting.event_id == Registration.event_id,
                  EventSetting.module == p.MODULE, EventSetting.name == db.func.concat('order_', Registration.id)))
                 .filter(Registration.event_id == self.event.id, ~Registration.is_deleted))
        state = request.args.get('state', '')
        if state:
            if state not in ('awaiting', 'review', 'paid', 'refund_requested', 'refunded', 'payment_exception'):
                raise BadRequest('Invalid order state.')
            query = query.filter(EventSetting.value['status'].astext == state)
        total = query.count()
        rows = query.order_by(Registration.id.desc()).offset((page - 1) * 25).limit(25).all()
        if request.path.endswith('.csv'):
            if total > 10000:
                raise Conflict('请按状态筛选后导出 / Filter orders before exporting more than 10000 rows.')
            stream = io.StringIO(newline='')
            writer = csv.writer(stream)
            writer.writerow(['订单号', '会议', '姓名', '邮箱', '金额', '币种', '状态', '付款方式', '到账流水', '退款流水', '发票号'])
            for registration in query.order_by(Registration.id).all():
                order = p.get_order(registration)
                payment, refund, invoice = order.get('payment') or {}, order.get('refund') or {}, order.get('invoice') or {}
                values = [order['number'], self.event.title, registration.full_name, registration.email,
                          order['amount'], 'CNY', order['status'], payment.get('provider', ''),
                          payment.get('reference', ''), refund.get('reference', ''), invoice.get('number', '')]
                writer.writerow(["'" + str(v) if str(v).lstrip().startswith(('=', '+', '-', '@')) else str(v) for v in values])
            result = make_response('\ufeff' + stream.getvalue())
            result.headers.update({'Content-Type': 'text/csv; charset=utf-8',
                                   'Content-Disposition': f'attachment; filename="conference-{self.event.id}-orders.csv"',
                                   'Cache-Control': 'private, no-store'})
            return result
        return response({'items': [p.serialize_order(reg, p.get_order(reg), finance=True) for reg in rows],
                         'total': total, 'page': page, 'can_confirm': session.user.is_admin})


class RHOrder(RHAccount):
    def _process_args(self):
        self.registration = Registration.get(request.view_args['registration_id'])
        if (not self.registration or self.registration.is_deleted or self.registration.registration_form.is_deleted
                or self.registration.event.is_deleted or not YujianSitePlugin.event_settings.get(
                    self.registration.event, 'company_collection', False)):
            raise NotFound()
        self.event = self.registration.event

    def _check_access(self):
        super()._check_access()
        if self.registration.user_id != session.user.id and not self.event.can_manage(session.user):
            raise Forbidden()
        if not self.event.can_manage(session.user) and not event_visible(self.event, session.user, 'registration'):
            raise Forbidden()
        check_event_locked(self, self.event)

    def _process(self):
        from .payment_gateways import available_gateways, checkout_public, start_checkout
        action = request.view_args.get('action')
        if request.method == 'POST':
            self.registration = p.lock_registration(self.registration)
            self._check_access()
            data = body()
            if action in ('confirm', 'refund-decision', 'invoice-issued'):
                if not session.user.is_admin:
                    raise Forbidden('仅公司财务管理员可确认 / Company administrator required.')
            elif self.registration.user_id != session.user.id:
                raise Forbidden('仅报名本人可提交 / Registration owner required.')
            if action == 'create':
                p.ensure_order(self.registration)
            elif action == 'transfer':
                p.transfer(self.registration, data)
            elif action == 'confirm':
                order = p.get_order(self.registration)
                if not order or order.get('checkout'):
                    raise Conflict('请通过对应支付渠道核对到账 / Verify through the selected payment channel.')
                p.confirm_payment(self.registration, order, p.required(data, 'reference', 120), amount=data.get('amount'))
            elif action == 'refund':
                p.apply_refund(self.registration, data)
            elif action == 'refund-decision':
                p.decide_refund(self.registration, data)
            elif action == 'invoice':
                p.apply_invoice(self.registration, data)
            elif action == 'invoice-issued':
                p.issue_invoice(self.registration, data)
            elif action == 'checkout':
                p.accept_terms(self.registration, data)
                return response(start_checkout(self.registration, data.get('provider')))
            else:
                raise NotFound()
        if request.path.endswith('/receipt/'):
            order = p.get_order(self.registration)
            if not order or order['status'] not in ('paid', 'refund_requested', 'refunded', 'payment_exception'):
                raise Conflict('到账后可查看付款确认单 / Confirmation is available after payment.')
            result = make_response(render_plugin_template('payment-receipt.html', registration=self.registration, order=order))
            result.headers['Cache-Control'] = 'private, no-store'
            return result
        if not request.path.startswith('/api/'):
            return render_plugin_template('builder.html', mode='payment-detail', event=self.event)
        saved_order = p.get_order(self.registration)
        result = p.serialize_order(self.registration, saved_order, finance=self.event.can_manage(session.user))
        result.update(gateways=available_gateways(), can_confirm=session.user.is_admin,
                      is_owner=self.registration.user_id == session.user.id,
                      payment_channel=(saved_order.get('checkout') or {}).get('provider') if saved_order else None,
                      checkout=checkout_public(saved_order.get('checkout')) if saved_order and self.registration.user_id == session.user.id else None)
        return response(result)


class RHGatewayNotify(RH):
    CSRF_ENABLED = False  # Provider callbacks authenticate the raw request with RSA signatures.

    def _process(self):
        from .payment_gateways import process_notification
        provider = request.view_args['provider']
        process_notification(provider)
        # Commit before acknowledging: providers must retry if recording the transaction fails.
        db.session.commit()
        return ('success', 200, {'Content-Type': 'text/plain'}) if provider == 'alipay' else ('', 204)


def register_routes(bp):
    bp.add_url_rule('/company/payments/', 'company_payments_page', RHCompanyPage)
    bp.add_url_rule('/api/company/payments/', 'company_payments', RHCompanySettings, methods=['GET', 'PUT'])
    bp.add_url_rule('/conference/<int:event_id>/payments/', 'fees_page', RHFeesPage)
    bp.add_url_rule('/api/conferences/<int:event_id>/fees', 'fees', RHFees, methods=['GET', 'PUT'])
    bp.add_url_rule('/api/conferences/<int:event_id>/orders', 'orders', RHOrders)
    bp.add_url_rule('/api/conferences/<int:event_id>/orders.csv', 'orders_csv', RHOrders)
    bp.add_url_rule('/payments/<int:registration_id>/', 'payment_page', RHOrder)
    bp.add_url_rule('/payments/<int:registration_id>/receipt/', 'payment_receipt', RHOrder)
    bp.add_url_rule('/api/payments/<int:registration_id>/', 'payment_detail', RHOrder)
    bp.add_url_rule('/api/payments/<int:registration_id>/<action>', 'payment_action', RHOrder, methods=['POST'])
    bp.add_url_rule('/api/payments/notify/<provider>', 'payment_notify', RHGatewayNotify, methods=['POST'])
