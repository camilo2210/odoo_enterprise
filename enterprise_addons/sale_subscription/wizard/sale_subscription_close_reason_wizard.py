# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.fields import Date
from odoo.exceptions import ValidationError


class SaleSubscriptionCloseReasonWizard(models.TransientModel):
    _name = 'sale.subscription.close.reason.wizard'
    _description = 'Subscription Close Reason Wizard'

    close_reason_id = fields.Many2one("sale.order.close.reason", string="Close Reason", required=True)
    close_date = fields.Date(required=True)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        res['close_date'] = sale_order.end_date if sale_order.end_date else Date.context_today(self)
        res['close_reason_id'] = sale_order.close_reason_id

        return res

    @api.model
    def new(self, values=None, origin=None, ref=None):
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        invoice_free = not any(
            state in ['draft', 'posted']
            for state in sale_order.order_line.sudo().invoice_lines.mapped('parent_state')
        )
        invoice_free = invoice_free and not self.env['account.move.line'].sudo().search([
            ('subscription_id', '=', sale_order.id),
            ('move_type', '=', 'out_invoice'),
            ('parent_state', 'in', ['draft', 'posted'])
        ], limit=1)
        if invoice_free:
            raise ValidationError(_("""You can not churn a contract that has not been invoiced. Please cancel the contract instead."""))
        return super().new(values=values, origin=origin, ref=ref)

    def set_close(self):
        self.ensure_one()
        sale_order = self.env['sale.order'].browse(self.env.context.get('active_id'))
        sale_order.close_reason_id = self.close_reason_id
        sale_order.end_date = self.close_date
        if self.close_date and self.close_date <= Date.context_today(self):
            sale_order.set_close(close_reason_id=self.close_reason_id.id)
