import logging
from odoo import _, api, fields, models
from odoo.exceptions import RedirectWarning, UserError

_logger = logging.getLogger(__name__)

STATUSES = [
    ('uninitiated', "Uninitiated"),
    ('unsigned', "Unsigned"),
    ('pending', "Pending"),
    ('accepted', "Accepted"),
    ('canceled', "Canceled"),
    ('rejected', "Rejected"),
]


class AccountOnlineLink(models.Model):
    _inherit = 'account.online.link'

    is_payment_enabled = fields.Boolean()
    is_payment_activation_requested = fields.Boolean(help="Technical field indicating whether the customer has started the payment activation process with the provider.")
    is_payment_activated = fields.Boolean()
    is_bulk_payment_activated = fields.Boolean(string="Bulk Payment Activated")
    is_single_payment_activated = fields.Boolean(string="Single Payment Activated")
    is_in_audit = fields.Boolean(readonly=True)
    is_payment_blocked = fields.Boolean(readonly=True)  # Since is_payment_enable will be reactivated, we need a way to block the payment

    def _update_payments_activated(self, data):
        self.ensure_one()

        if data.get('is_payment_enabled') is not None:
            self.is_payment_enabled = data['is_payment_enabled']

        if data.get('is_payment_activation_requested') is not None:
            self.is_payment_activation_requested = data['is_payment_activation_requested']

        if data.get('is_payment_activated') is not None:
            self.is_payment_activated = data['is_payment_activated']

    def _update_connection_status(self):
        data = super()._update_connection_status()

        self._update_payments_activated(data)
        self._update_audit_status(data)

        return data

    def _update_audit_status(self, data):
        """ Synchronizes the audit and payment disabled statuses for all payment-enabled connections.

            Searches for connections where payment is enabled but the current audit or payment disabled
            status differs from the provided data, and updates them to match.
        """
        is_in_audit = data.get('is_in_audit')
        is_payment_blocked = data.get('is_payment_blocked')

        self.sudo().search([
            '&',
            ('is_payment_enabled', '=', True),
            '|',
            ('is_in_audit', '!=', is_in_audit),
            ('is_payment_blocked', '!=', is_payment_blocked),
        ]).write({
            'is_in_audit': is_in_audit,
            'is_payment_blocked': is_payment_blocked,
        })

    def _activate_payments(self):
        self.ensure_one()

        if not self.is_payment_enabled:
            raise UserError(_('To activate payments, you must first enable them when connecting a bank account.'))

        if self.is_payment_activated:
            raise UserError(_('Payments are already activated.'))

        if self.is_payment_activation_requested:
            raise UserError(_('Payment activation process is already in progress.'))

        data = {}
        try:
            while True:
                response = self._fetch_odoo_fin('/proxy/v1/activate_payments', data)
                next_data = response.get('next_data')
                if not next_data:
                    break
                data['next_data'] = next_data

            return {
                'type': 'ir.actions.act_url',
                'url': response['redirect_url'],
                'target': '_blank',
            }
        except RedirectWarning as e:
            if 'The payments initiation service is already activated for this connection.' in str(e):
                self.is_payment_activated = True
            raise

    def action_activate_payments(self):
        self.ensure_one()
        return self._activate_payments()

    def _success_link(self):
        action = super()._success_link()

        try:
            response = self._activate_payments()
            if not response:
                return action

            if template := self.env.ref('account_online_payment.mail_template_account_payment_activation', raise_if_not_found=False):
                template.with_context(url=response['url']).send_mail(self.id)

            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=self.env.user.id,
                summary=_("Complete your KYC"),
                note=_("You haven't completed your KYC yet, so you can't process payment directly from Odoo."),
            )
            return action if action else {
                'type': 'ir.actions.client',
                'tag': 'soft_reload',
            }
        except UserError as e:
            _logger.warning("Non-blocking error during payment activation: %s", e)
            return action

    def _initiate_payment(self, record):
        record.ensure_one()
        assert record._name in {'account.payment', 'account.batch.payment'}, "This method should only be called with account.payment or account.batch.payment record."
        data = record._prepare_payment_data()
        while True:
            response = self._fetch_odoo_fin('/proxy/v2/initiate_payment', data)
            # In case of token expiration, we receive a special next_data field that we use to redo the request
            if not response.get('next_data'):
                break
            data['next_data'] = response['next_data']

        record._send_after_validation()
        record.write({
            'payment_identifier': response.get('payment_identifier'),
            'payment_online_status': response.get('payment_online_status'),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': response.get('redirect_url'),
            'target': '_blank',
        }

    @api.model
    def _sign_payment(self, record):
        record.ensure_one()
        assert record._name in {'account.payment', 'account.batch.payment'}, "This method should only be called with account.payment or account.batch.payment records."
        account_online_link = record.journal_id.account_online_link_id
        data = record._prepare_payment_data()
        data['payment_identifier'] = record.payment_identifier
        while True:
            response = account_online_link._fetch_odoo_fin('/proxy/v1/sign_payment', data)

            if not response.get('next_data'):
                break
            data['next_data'] = response['next_data']

        record.payment_online_status = response['payment_online_status']
        record.payment_identifier = response['payment_identifier']

        return {
            'type': 'ir.actions.act_url',
            'url': response['redirect_url'],
            'target': '_blank',
        }

    @api.model
    def check_online_payment_status(self, res_ids, res_model):
        assert res_model in {'account.payment', 'account.batch.payment'}, "You can only call this method with payments or batch payments"
        statuses = {}
        records = self.env[res_model].browse(res_ids)
        for record in records:
            account_online_account = record.journal_id.account_online_account_id
            if not account_online_account:
                raise UserError(self.env._("This journal needs to be connected to a bank to check its payments status."))

            data = {
                'payment_identifier': record.payment_identifier,
                'account_id': account_online_account.online_identifier,
                'payment_type': 'bulk' if res_model == 'account.batch.payment' else 'single',
            }
            response = record.journal_id.account_online_link_id._fetch_odoo_fin('/proxy/v2/get_payment_status', data)

            record.payment_online_status = response.get('payment_online_status')
            statuses[record.id] = record.payment_online_status

        return statuses

    @api.model
    def _cron_check_payment_status(self):
        domain = [
            ('state', '!=', 'reconciled'),
            ('journal_id.account_online_link_id.is_payment_activated', '=', True),
            ('payment_online_status', 'in', ('unsigned', 'pending')),
        ]
        batch_payments = self.env['account.batch.payment'].search(domain)
        self.check_online_payment_status(batch_payments.ids, batch_payments._name)

        payments = self.env['account.payment'].search(domain)
        self.check_online_payment_status(payments.ids, payments._name)
