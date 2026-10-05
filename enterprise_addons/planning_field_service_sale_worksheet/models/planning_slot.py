from odoo import models
from odoo.fields import Domain


class PlanningSlot(models.Model):
    _inherit = 'planning.slot'

    def _domain_worksheet_template_id(self):
        if sale_line_id := self.env.context.get('default_sale_line_id'):
            sale_line = self.env['sale.order.line'].browse(sale_line_id)
            if sale_line.product_id.planning_enabled and sale_line.product_id.worksheet_template_id:
                return sale_line.product_id.worksheet_template_id
        return super()._domain_worksheet_template_id()

    def _get_currency_field(self):
        return self.currency_id

    def _get_is_intervention_report_available_domain(self):
        field_service_sale_timesheet_domain = Domain([
            '|', '|',
            ('under_warranty', '=', False),
            ('sale_order_id', '!=', False),
            '&', ('allow_timesheets', '=', True), ('intervention_timesheet_ids', '!=', False),
        ])
        field_service_worksheet_domain = Domain([('worksheet_template_id', '!=', False)])
        return field_service_sale_timesheet_domain | field_service_worksheet_domain
