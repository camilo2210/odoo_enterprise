from odoo import api, fields, models


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    under_warranty = fields.Boolean(compute='_compute_under_warranty', store=True, readonly=False)

    @api.depends('sale_line_id.order_id.subscription_state')
    def _compute_under_warranty(self):
        if not self.env.user.has_group('planning_field_service_stock_subscription.group_field_service_allow_maintenance_contract'):
            return
        for slot in self:
            slot.under_warranty = slot.sale_order_id.subscription_state == '3_progress'

    @api.depends('sale_line_id.lot_ids')
    def _compute_lot_ids(self):
        if not self.env.user.has_group('planning.group_field_service_allow_equipment'):
            return
        if not self.env.user.has_group('planning_field_service_stock_subscription.group_field_service_allow_maintenance_contract'):
            return super()._compute_lot_ids()

        lots_per_sale_line = {
            sale_line: sale_line.lot_ids
            for sale_line in self.sudo().sale_line_id
            if sale_line.lot_ids
        }
        shifts_from_sale_line = self.filtered(lambda s: s.sale_line_id in lots_per_sale_line)
        for slot in shifts_from_sale_line:
            slot.lot_ids = lots_per_sale_line[slot.sale_line_id]

        shifts_without_contract = self - shifts_from_sale_line
        shifts_without_contract.lot_ids = False
        super(PlanningSlot, shifts_without_contract)._compute_lot_ids()
