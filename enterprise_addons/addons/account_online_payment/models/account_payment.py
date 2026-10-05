from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain

from odoo.addons.account.tools.structured_reference import is_valid_structured_reference_for_country
from odoo.addons.account_online_payment.models.account_online_link import STATUSES

ONLINE_STATUS_TO_STATE = {
    'uninitiated': 'draft',
    'unsigned': 'draft',
    'pending': 'paid',
    'accepted': 'paid',
    'rejected': 'rejected',
    'canceled': 'canceled',
}

PAYABLE_ONLINE_STATUSES = {'uninitiated', 'unsigned'}


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    payment_identifier = fields.Char(string="Payment ID", readonly=True, copy=False)
    payment_online_status = fields.Selection(selection=STATUSES, string="PIS Status", default='uninitiated', readonly=True, copy=False)
    could_initiate_payment = fields.Boolean(string="Could Initiate Payment", compute='_compute_could_initiate_payment', search='_search_could_initiate_payment')
    show_connect_bank_button = fields.Boolean(compute='_compute_payment_action_buttons')
    show_activate_payments_button = fields.Boolean(compute='_compute_payment_action_buttons')
    payment_method_code = fields.Char(related='payment_method_line_id.code')
    payment_method_placeholder = fields.Char(compute='_compute_payment_method_placeholder')

    @api.depends(
        'journal_id.type',
        'journal_id.account_online_link_id.is_payment_activated',
        'partner_bank_id.allow_out_payment',
        'payment_type',
        'payment_online_status',
        'batch_payment_id.payment_online_status',
    )
    def _compute_could_initiate_payment(self):
        # This field tells if the payment meets the condition to be paid online, so we don't have
        # to check if the journal is sync, the flow will be different depending on if the journal
        # is sync or not.
        for payment in self:
            payment.could_initiate_payment = (
                payment.payment_type == 'outbound' and
                payment.journal_id.type == 'bank' and
                payment.journal_id.account_online_link_id.is_payment_activated and
                payment.partner_bank_id.allow_out_payment and
                (
                    # A standalone payment uses its own status; a batched payment uses its batch's status.
                    payment.payment_online_status in PAYABLE_ONLINE_STATUSES
                    if not payment.batch_payment_id
                    else payment.batch_payment_id.payment_online_status in PAYABLE_ONLINE_STATUSES
                )
            )

    def _search_could_initiate_payment(self, operator, value):
        if operator not in {'=', '!='} or value not in {True, False}:
            return NotImplemented

        domain = Domain([
            ('payment_type', '=', 'outbound'),
            ('journal_id.type', '=', 'bank'),
            ('journal_id.account_online_link_id.is_payment_activated', '=', True),
            ('partner_bank_id.allow_out_payment', '=', True),
            '|',
                '&',
                    ('batch_payment_id', '=', False),
                    ('payment_online_status', 'in', PAYABLE_ONLINE_STATUSES),
                ('batch_payment_id.payment_online_status', 'in', PAYABLE_ONLINE_STATUSES),
        ])
        if operator == '=' and value is True or operator == '!=' and value is False:
            return domain

        return ~domain

    @api.depends(
        'could_initiate_payment',
        'payment_type',
        'journal_id.account_online_link_id',
        'journal_id.account_online_link_id.is_payment_enabled',
        'journal_id.account_online_link_id.is_payment_activated',
    )
    def _compute_payment_action_buttons(self):
        for payment in self:
            is_outbound = payment.payment_type == 'outbound'
            online_link = payment.journal_id.account_online_link_id
            journal_allows_initiation = online_link.is_payment_activated
            payment.show_connect_bank_button = is_outbound and (not online_link or not online_link.is_payment_enabled)
            payment.show_activate_payments_button = (
                is_outbound
                and online_link
                and online_link.is_payment_enabled
                and not journal_allows_initiation
            )

    @api.depends('payment_method_line_id')
    def _compute_payment_method_placeholder(self):
        for payment in self:
            payment.payment_method_placeholder = self.env._("Bank Connection") if payment.payment_method_line_id.code == 'sepa_ct' and payment.payment_identifier else None

    def action_connect_bank(self):
        self.ensure_one()
        return self.journal_id.account_online_link_id.action_new_synchronization(journal_id=self.journal_id.id)

    def action_activate_payments(self):
        self.ensure_one()
        return self.journal_id.account_online_link_id.action_activate_payments()

    def _send_after_validation(self):
        self.mark_as_sent()

    def _sync_payment_state_from_online_status(self, payment_online_status):
        draft_payments = self.env['account.payment']
        paid_payments = self.env['account.payment']
        rejected_payments = self.env['account.payment']
        canceled_payments = self.env['account.payment']

        for payment in self:
            target_state = ONLINE_STATUS_TO_STATE[payment_online_status]
            if target_state == 'draft' and payment.state != 'draft':
                draft_payments |= payment
            elif target_state == 'paid' and payment.state != 'paid':
                paid_payments |= payment
            elif target_state == 'rejected' and payment.state != 'rejected':
                rejected_payments |= payment
            elif target_state == 'canceled' and payment.state != 'canceled':
                canceled_payments |= payment

        if draft_payments:
            draft_payments.action_draft()
        if paid_payments:
            paid_payments.action_post()
        if rejected_payments:
            rejected_payments.action_reject()
        if canceled_payments:
            canceled_payments.action_cancel()

    def _get_payment_data(self):
        country_code = self.partner_bank_id.sanitized_account_number[:2]
        payment_data = {
            'amount': self.amount,
            'account_number': self.partner_bank_id.sanitized_account_number,
            'account_type': 'IBAN',
            'creditor_name': self.partner_id.name,
            'currency': self.currency_id.display_name,
            'date': fields.Date.to_string(self.date),
            'reference': self.memo,
            'structured_reference': is_valid_structured_reference_for_country(self.memo, country_code),
            'transaction_uuid': self.transaction_uuid,
        }

        if vat := self.partner_id.vat:
            payment_data['creditor_identification'] = vat
        if address := self.partner_id.contact_address_inline:
            payment_data['creditor_address'] = address

        return payment_data

    def _detach_from_batch(self):
        """ Removes the payments in `self` from their batches. """
        if any(payment.state != 'draft' for payment in self):
            raise UserError(self.env._("Only draft payments can be detached from a batch."))

        batches = self.batch_payment_id
        self.write({
            'batch_payment_id': False,
            'is_sent': False,
        })
        if empty_batches := batches.filtered(lambda b: not b.payment_ids):
            empty_batches.unlink()

    def _prepare_payment_data(self):
        self.ensure_one()
        data = {
            'account_id': self.journal_id.account_online_account_id.online_identifier,
            'batch_booking': False,
            'date': fields.Date.to_string(self.date),
            'payer_account_number': self.journal_id.account_online_account_id.account_number,
            'payer_name': self.journal_id.company_id.name,
            'payment_type': 'single',
            'payments': [self._get_payment_data()],
        }

        if vat := self.journal_id.company_id.vat:
            data['payer_identification'] = vat
        if address := self.journal_id.company_id.partner_id.contact_address_inline:
            data['payer_address'] = address

        return data

    def write(self, vals):
        result = super().write(vals)
        if 'payment_online_status' in vals:
            self._sync_payment_state_from_online_status(vals['payment_online_status'])
        return result

    def action_draft(self):
        if (
            not self.env.context.get('bypass_batch_payment_online_status_protection')
            and any(
                (
                    payment.batch_payment_id.payment_online_status
                    if payment.batch_payment_id
                    else payment.payment_online_status
                ) in {'pending', 'accepted'}
                for payment in self
            )
        ):
            raise UserError(self.env._("You cannot modify a payment that has already been sent to the bank."))

        return super().action_draft()

    def _prepare_payment_retry(self):
        """
        Prepares selected payments for a new attempt, discarding any previous local attempt if necessary.
        Returns an action to sign in case we have one unsigned payment not in a batch.
        """
        # Retry flow:
        # - A standalone unsigned payment keeps its provider attempt and is signed directly.
        # - Multiple standalone unsigned payments discard their previous local attempt and are
        #   reinitiated in a new batch, together with any selected uninitiated payments.
        # - Selected payments in an uninitiated or unsigned batch are detached so they can join
        #   that new attempt; unselected payments remain in the original batch.
        # Online status is stored on standalone payments, but on batches for grouped payments.
        standalone_payments = self.filtered(lambda payment: not payment.batch_payment_id)
        if (
            any(payment.payment_online_status not in PAYABLE_ONLINE_STATUSES for payment in standalone_payments)
            or any(batch.payment_online_status not in PAYABLE_ONLINE_STATUSES for batch in self.batch_payment_id)
        ):
            raise UserError(self.env._("Only uninitiated or unsigned payments can be retried."))

        if unsigned_payments := standalone_payments.filtered(lambda payment: payment.payment_online_status == 'unsigned'):
            if len(self) == 1 and not self.batch_payment_id:
                return self.action_sign()
            # Multiple payments require a new provider batch. Clear stale local identifiers so
            # subsequent status updates are associated only with the replacement attempt.
            unsigned_payments.filtered(lambda payment: not payment.batch_payment_id).write({
                'is_sent': False,
                'payment_identifier': False,
                'payment_online_status': 'uninitiated',
            })

        # Detach selected payments only; the original batch may retain unselected payments.
        if self.batch_payment_id:
            self._detach_from_batch()

    def _execute_payment_initiation(self):
        self.journal_id.account_online_account_id._check_payment_limit_exceeded(self)

        if len(self) > 1:
            batch_payment, batch_payment_action = self._create_and_validate_batch_payment(initiate_payment=True)
            if not batch_payment:
                return batch_payment_action

            if batch_payment_action:
                if batch_payment_action.get('res_model') == 'account.batch.error.wizard':
                    return batch_payment_action

                batch_payment_action['close'] = True
                return batch_payment_action

        action = self.journal_id.account_online_link_id._initiate_payment(self)
        action['close'] = True
        return action

    def action_pay(self):
        """Initiate selected payments online, signing one unsigned standalone payment when applicable.

        Multiple selected payments are initiated together in a new batch. Existing unsigned
        standalone attempts are discarded locally before being retried in that batch.
        """
        if not self:
            raise UserError(self.env._("You must select at least one payment."))

        if any(payment.payment_type != 'outbound' for payment in self):
            raise UserError(self.env._("Only outbound payments can be paid online."))

        if len(self.journal_id) > 1:
            raise UserError(self.env._("You can't pay payments from more than one journal."))

        if self.journal_id.type != 'bank':
            raise UserError(self.env._("Online payments require a bank journal."))

        if any(not payment.partner_bank_id.allow_out_payment for payment in self):
            raise UserError(self.env._("The recipient bank account must be allowed for outgoing payments."))

        if len(self.payment_method_line_id) > 1:
            raise UserError(self.env._("All payments must have the same payment method."))

        if not self.journal_id.account_online_link_id.is_payment_activated:
            raise UserError(self.env._("The payment initiation service is not activated for this journal."))

        if action := self._prepare_payment_retry():
            return action

        return self._execute_payment_initiation()

    def action_sign(self):
        self.ensure_one()
        self.journal_id.account_online_account_id._check_payment_limit_exceeded(self)

        action = self.journal_id.account_online_link_id._sign_payment(self)
        action['close'] = True
        return action
