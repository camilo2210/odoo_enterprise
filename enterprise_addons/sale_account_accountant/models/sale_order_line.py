from odoo import _, api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    unit_cost = fields.Float(string="Cost by Unit", related='product_id.standard_price', groups='base.group_user')
    total_cost = fields.Float(string="Total Cost", compute='_compute_total_cost', groups='base.group_user')

    @api.depends('qty_delivered_at_date', 'qty_invoiced_at_date', 'product_id.standard_price')
    def _compute_total_cost(self):
        for line in self:
            line = line.with_company(line.company_id)
            line.total_cost = (line.qty_delivered_at_date - line.qty_invoiced_at_date) * line.product_id.standard_price

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[tuple]:
        return self._read_group_for_accrual(domain, groupby, aggregates, having, offset, limit, order)

    @api.model
    def _get_aggregates_to_skip_and_fields_to_patch(self):
        aggregates_to_skip, fields_to_patch = super()._get_aggregates_to_skip_and_fields_to_patch()
        aggregates_to_skip.insert(0, 'qty_delivered_at_date:sum')
        fields_to_patch.insert(0, 'qty_delivered_at_date')
        return (aggregates_to_skip, fields_to_patch)

    def action_open_accrual_wizard(self):
        match accrual_type := self.env.context.get('accrual_type'):
            case 'invoice_to_be_issued':
                action_name = _('Create Invoices to be Issued Entry')
            case 'invoiced_not_delivered':
                action_name = _('Create Invoiced Not Delivered Entry')
            case _other:
                action_name = _('Accrued Revenue Entry')

        return {
            'name': action_name,
            'type': 'ir.actions.act_window',
            'res_model': 'account.accrued.orders.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                **self.env.context,
                'default_accrual_type': accrual_type,
            },
        }
