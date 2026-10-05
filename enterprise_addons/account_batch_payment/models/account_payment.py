# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, models, fields, api, _
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    batch_payment_id = fields.Many2one('account.batch.payment', ondelete='set null', copy=False, index='btree_not_null')
    payment_method_name = fields.Char(related='payment_method_line_id.name')
    batch_payments_count = fields.Char(compute='_compute_batch_payments_count')
    show_download_xml_button = fields.Boolean(compute='_compute_show_download_xml_button')

    @api.depends('batch_payment_id.payment_ids')
    def _compute_batch_payments_count(self):
        for payment in self:
            payment.batch_payments_count = len(payment.batch_payment_id.payment_ids)

    @api.depends('payment_type', 'payment_method_line_id.code')
    def _compute_show_download_xml_button(self):
        exportable_method_codes = self.env['account.batch.payment']._get_methods_generating_files()
        for payment in self:
            payment.show_download_xml_button = (
                payment.payment_type == 'outbound'
                and payment.payment_method_line_id.code in exportable_method_codes
            )

    def _create_and_validate_batch_payment(self, initiate_payment=False):
        batch_payment_action = self.create_batch_payment()
        if batch_payment_action['res_model'] != 'account.batch.payment':
            return self.env['account.batch.payment'], batch_payment_action

        batch_payment = self.batch_payment_id
        return batch_payment, batch_payment.validate_batch(initiate_payment=initiate_payment)

    @api.model
    def create_batch_payment(self):
        valid_payment_states = ['draft', *self._valid_payment_states()]
        if any(payment.state not in valid_payment_states for payment in self):
            create_batch_error_wizard = self.env['account.create.batch.error.wizard'].create({'payment_ids': [Command.set(self.ids)]})
            return {
                'name': _('Create Batch'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'target': 'new',
                'res_model': 'account.create.batch.error.wizard',
                'res_id': create_batch_error_wizard.id,
            }

        # We use self[0] to create the batch; the constrains on the model ensure
        # the consistency of the generated data (same journal, same payment method, ...)
        batch = self.env['account.batch.payment'].create({
            'journal_id': self[0].journal_id.id,
            'payment_ids': [(4, payment.id, None) for payment in self],
            'payment_method_id': self[0].payment_method_id.id,
            'batch_type': self[0].payment_type,
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.batch.payment",
            "views": [[False, "form"]],
            "res_id": batch.id,
        }

    def button_open_batch_payment(self):
        ''' Redirect the user to the batch payments containing this payment.
        :return:    An action on account.batch.payment.
        '''
        self.ensure_one()

        return {
            'name': _("Batch Payment"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'context': {'create': False},
            'view_mode': 'form',
            'res_id': self.batch_payment_id.id,
        }

    def write(self, vals):
        old_batch_payments = {payment: payment.batch_payment_id for payment in self}
        result = super().write(vals)
        if 'batch_payment_id' not in vals:
            return result
        batch_payment_id = vals.get('batch_payment_id')
        batch_payment = self.env['account.batch.payment'].browse(batch_payment_id) if batch_payment_id else None
        for payment in self:
            if batch_payment:
                payment.message_post(
                    body=_('Payment added in batch %s', batch_payment._get_html_link(title=batch_payment.name)),
                    message_type='comment',
                )
            elif old_batch_payments.get(payment):
                payment.message_post(
                    body=_('Payment removed from batch %s', old_batch_payments[payment]._get_html_link(title=old_batch_payments[payment].name)),
                    message_type='comment',
                )
        return result

    def action_download_xml(self):
        if not self:
            raise UserError(self.env._("You must select at least one payment to generate a file."))

        if any(payment.payment_type != 'outbound' for payment in self):
            raise UserError(self.env._("Only outbound payments can be exported."))

        if len(self.journal_id) > 1:
            raise UserError(self.env._("You can't generate a file for payments from more than one journal."))

        if len(self.payment_method_line_id) > 1:
            raise UserError(self.env._("All payments must have the same payment method."))

        if self.payment_method_line_id.code not in self.env['account.batch.payment']._get_methods_generating_files():
            raise UserError(self.env._("Selected payments include methods that cannot generate a file."))

        self.action_post()

        batch_payment, batch_payment_action = self._create_and_validate_batch_payment()
        if not batch_payment:
            return batch_payment_action
        if batch_payment_action and batch_payment_action.get('res_model') == 'account.batch.error.wizard':
            return batch_payment_action

        if not batch_payment.export_file_attachment_id:
            batch_payment.with_context(xml_export=True).export_batch_payment()

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{batch_payment.export_file_attachment_id.id}?download=true',
            'close': True,
        }
