# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    planning_slot_id = fields.Many2one('planning.slot', 'Intervention', index='btree_not_null')

    @api.depends('planning_slot_id.sale_line_id', 'planning_slot_id.under_warranty')
    def _compute_so_line(self):
        super()._compute_so_line()

    def action_view_field_service_intervention(self):
        self.ensure_one()
        return self.planning_slot_id.with_context({'create': 0})._get_records_action()

    def _timesheet_determine_sale_line(self):
        if self.project_id and self.planning_slot_id:  # field service intervention
            if self.planning_slot_id.under_warranty:
                return self.planning_slot_id.sale_line_id if self.planning_slot_id.sale_line_id and self.planning_slot_id.sale_line_id.price_unit == 0 else False
            else:
                # Then we want to keep the SOL define for this timesheet
                if not self.planning_slot_id.sale_line_id:
                    return False
                product = self.employee_id.timesheet_product_id
                sol = False
                if product:
                    sol = product and self.env['sale.order.line'].search([
                        ('product_id', '=', product.id),
                        ('order_id', '=', self.planning_slot_id.sale_order_id.id),
                    ], limit=1)
                return sol or self.planning_slot_id.sale_line_id
        return super()._timesheet_determine_sale_line()
