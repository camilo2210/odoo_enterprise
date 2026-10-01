from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    field_service_travel_fees_mode = fields.Selection(
        related="company_id.field_service_travel_fees_mode",
        readonly=False,
    )
    travel_time_invoicing_product_id = fields.Many2one(related="company_id.travel_time_invoicing_product_id", readonly=False)
    planning_project_id = fields.Many2one(
        'project.project',
        related='company_id.planning_project_id',
        readonly=False,
    )

    @api.onchange('field_service_travel_fees')
    def _onchange_field_service_travel_fees(self):
        if not self.field_service_travel_fees:
            self.field_service_travel_fees_mode = 'fixed'
            return

        if not self.travel_time_invoicing_product_id:
            self.travel_time_invoicing_product_id = self.env.ref(
                'planning_field_service_sale_timesheet.field_service_product_travel_invoice',
                raise_if_not_found=False,
            )
