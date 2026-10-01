from odoo import _, api, fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_categ_id = fields.Many2one(related='product_id.categ_id')

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[tuple]:
        return self._read_group_for_accrual(domain, groupby, aggregates, having, offset, limit, order)

    @api.model
    def _get_aggregates_to_skip_and_fields_to_patch(self):
        aggregates_to_skip, fields_to_patch = super()._get_aggregates_to_skip_and_fields_to_patch()
        aggregates_to_skip.insert(0, 'qty_received_at_date:sum')
        fields_to_patch.insert(0, 'qty_received_at_date')
        return (aggregates_to_skip, fields_to_patch)

    def action_open_accrual_wizard(self):
        match accrual_type := self.env.context.get('accrual_type'):
            case 'bill_to_receive':
                action_name = _('Create Bills to Receive Entry')
            case 'billed_not_received':
                action_name = _('Create Billed not Received Entry')
            case _other:
                action_name = _('Accrued Expense Entry')

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
