from odoo import api, fields, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    is_payment_activated = fields.Boolean(related='journal_id.account_online_link_id.is_payment_activated')
    could_initiate_payment = fields.Boolean(compute='_compute_could_initiate_payment')
    is_payment_blocked = fields.Boolean(related='journal_id.account_online_link_id.is_payment_blocked')

    @api.depends('journal_id', 'partner_bank_id', 'available_payment_method_line_ids')
    def _compute_could_initiate_payment(self):
        for wizard in self:
            partner_bank_ids = {batch['payment_values']['partner_bank_id'] for batch in wizard.batches if batch['payment_values']['partner_bank_id']}
            # When the partner_bank_id from the move is empty, we want to take the one from the wizard itself
            if not partner_bank_ids and wizard.partner_bank_id:
                partner_bank_ids = {wizard.partner_bank_id.id}

            wizard.could_initiate_payment = (
                wizard.journal_id.type == 'bank' and
                wizard.journal_id.account_online_link_id.is_payment_activated and
                set(wizard.line_ids.move_id.mapped('move_type')) <= {'in_invoice', 'out_refund'} and
                partner_bank_ids and
                all(partner_bank.allow_out_payment for partner_bank in self.env['res.partner.bank'].browse(partner_bank_ids))
            )

    @api.depends('payment_type', 'journal_id')
    def _compute_payment_method_line_id(self):
        super()._compute_payment_method_line_id()
        for wizard in self:
            sepa_ct_payment_method = wizard.available_payment_method_line_ids.filtered(lambda pml: pml.code == 'sepa_ct')
            if sepa_ct_payment_method and wizard.could_initiate_payment:
                wizard.payment_method_line_id = sepa_ct_payment_method.id

    def action_create_payments(self):
        if not self.could_initiate_payment:
            return super().action_create_payments()

        payment_ids = self._create_payments()
        payment_ids.state = 'paid'
        payment_ids.journal_id.account_online_account_id._check_payment_limit_exceeded(payment_ids)
        if len(payment_ids) == 1:
            action = payment_ids.journal_id.account_online_link_id._initiate_payment(payment_ids)
        else:
            batch_payment_action = payment_ids.create_batch_payment()
            if batch_payment_action['res_model'] == 'account.batch.payment':
                batch_payment = self.env['account.batch.payment'].browse(batch_payment_action['res_id'])
                batch_payment_action = batch_payment.validate_batch(initiate_payment=True)
                action = batch_payment_action
            else:
                action = batch_payment_action

        action['close'] = True
        return action

    def action_sign_later(self):
        """Create payments in draft without posting/reconciling them."""
        payments = self.with_context(sign_later=True)._create_payments()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': self.env._("Payment created"),
                'message': self.env._("You can find %s in the payment view."),
                'links': [{
                    'label': payments.display_name if len(payments) == 1 else self.env._("the payments"),
                    'url': '/odoo/vendor-payments',
                }],
                'next': {
                    'type': 'ir.actions.act_window_close'
                },
            }
        }

    def _post_payments(self, to_process, edit_mode=False):
        # action_sign_later reuses _create_payments but must keep payments in draft.
        # Sign-later is used to create payments in draft to be paid in batch later.
        if self.env.context.get('sign_later'):
            return
        super()._post_payments(to_process, edit_mode=edit_mode)
