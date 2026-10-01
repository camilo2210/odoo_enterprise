from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError

from odoo.addons.account_online_payment.models.account_online_link import STATUSES


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    payment_identifier = fields.Char(string='Batch ID', readonly=True, copy=False)
    payment_online_status = fields.Selection(selection=STATUSES, string='PIS Status', default='uninitiated', readonly=True, copy=False)
    account_online_link_payments_enabled = fields.Boolean(compute='_compute_account_online_link_payments_enabled')
    account_online_link_payments_requested = fields.Boolean(related='journal_id.account_online_link_id.is_payment_activation_requested')
    account_online_link_payments_activated = fields.Boolean(related='journal_id.account_online_link_id.is_payment_activated')

    def activate_payments(self):
        """Redirect user to start the payment activation process"""
        self.ensure_one()
        online_link = self.journal_id.account_online_link_id

        if not online_link:
            raise UserError(_('No online bank connection found for this journal.'))

        if not online_link.is_payment_enabled:
            raise UserError(_('Payments are not enabled for this bank connection.'))

        if online_link.is_payment_activated:
            raise UserError(_('Payments are already activated for this bank connection.'))

        if online_link.is_payment_activation_requested:
            raise UserError(_('Payment activation process is already in progress for this bank connection.'))

        return online_link._activate_payments()

    def initiate_payment(self):
        """
        This function handles the two currently supported flows for validating batch payments:
        - Signing the payment online through Odoofin
        - Using the regular batch validation and exporting an SCT XML file
        """
        self.ensure_one()

        if self.payment_online_status == 'unsigned' and self.state == 'sent':
            self.env['account.online.link'].check_online_payment_status(self.ids, self._name)
            if self.payment_online_status != 'unsigned':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Payment already been signed'),
                        'message': _('This payment might have already been signed. Refreshing the payment status...'),
                        'type': 'warning',
                        'next': {
                            'type': 'ir.actions.client',
                            'tag': 'soft_reload',
                        },
                    },
                }

            return self.journal_id.account_online_link_id._sign_payment(self)
        return self.with_context(xml_export=False).validate_batch(initiate_payment=True)

    def validate_batch(self, initiate_payment=False):
        if not initiate_payment or not self.account_online_link_payments_enabled or self.env.context.get('xml_export'):
            return super().validate_batch(initiate_payment=initiate_payment)

        action = self._check_batch_validity()
        if action and action.get('res_model') == 'account.batch.error.wizard':
            return action

        account_online_link = self.journal_id.account_online_link_id
        self.journal_id.account_online_account_id._check_payment_limit_exceeded(self.payment_ids)

        return account_online_link._initiate_payment(self)

    def check_online_payment_status(self):
        return self.env['account.online.link'].check_online_payment_status(self.ids, self._name)

    def export_batch_payment(self):
        to_be_exported = self.env['account.batch.payment']

        for record in self:
            if record.account_online_link_payments_enabled and not self.env.context.get('xml_export'):
                continue
            to_be_exported += record

        super(AccountBatchPayment, to_be_exported).export_batch_payment()
        if any(payment.payment_online_status in {'pending', 'accepted'} for payment in to_be_exported):
            self.with_user(SUPERUSER_ID).message_post(body=_("Please be aware that signed payments may have already been processed and sent to the bank."))

    @api.depends('journal_id.account_online_link_id')
    def _compute_account_online_link_payments_enabled(self):
        for batch in self:
            batch.account_online_link_payments_enabled = batch.journal_id.account_online_link_id.is_payment_enabled

    def _prepare_payment_data(self):
        self.ensure_one()

        payment_data = {
            "account_id": self.journal_id.account_online_account_id.online_identifier,
            "batch_booking": self.iso20022_batch_booking,
            "date": fields.Date.to_string(self.date),
            "payer_account_number": self.journal_id.account_online_account_id.account_number,
            "payer_account_type": 'iban',
            "payer_account_holder_name": self.journal_id.bank_account_id.holder_name,
            "payer_name": self.journal_id.company_id.name,
            "payment_type": "bulk",
            "payments": [payment._get_payment_data() for payment in self.payment_ids],
            "reference": self.name,
        }

        if vat := self.journal_id.company_id.vat:
            payment_data["payer_identification"] = vat
        if address := self.journal_id.company_id.partner_id.contact_address_inline:
            payment_data["payer_address"] = address

        return payment_data

    def write(self, vals):
        result = super().write(vals)
        if 'payment_online_status' in vals:
            self.payment_ids._sync_payment_state_from_online_status(vals['payment_online_status'])
        return result
