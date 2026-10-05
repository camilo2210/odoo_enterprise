# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    module_project_forecast = fields.Boolean(string="Project Planning", default=False)
    module_planning_field_service = fields.Boolean(string="Field Service")
    planning_generation_interval = fields.Integer("Rate Of Shift Generation", required=True,
        related="company_id.planning_generation_interval", readonly=False)

    planning_employee_unavailabilities = fields.Selection(
        related="company_id.planning_employee_unavailabilities",
        readonly=False,
    )

    planning_self_unassign_days_before = fields.Integer(
        "Days before shift for unassignment",
        related="company_id.planning_self_unassign_days_before",
        readonly=False
    )

    # Field Service features
    module_planning_field_service_sale_timesheet = fields.Boolean(string="Billing")
    module_planning_field_service_worksheet = fields.Boolean(string="Worksheets")
    module_website_planning_field_service = fields.Boolean()
    module_planning_field_service_stock = fields.Boolean()
    website_planning_field_service = fields.Boolean(
        related='company_id.website_planning_field_service', readonly=False,
        string="Website Form")
    group_field_service_allow_geolocation = fields.Boolean(
        "Geolocation",
        implied_group='planning.group_field_service_allow_geolocation',
        help="Track technicians' location on a live map during work hours.",
    )
    group_field_service_allow_customer_report = fields.Boolean(
        "Customer Report",
        implied_group='planning.group_field_service_allow_customer_report',
    )
    group_field_service_allow_material = fields.Boolean("Products on Shifts", implied_group='planning.group_field_service_allow_material')
    group_field_service_hide_price = fields.Boolean("Hide Price", implied_group='planning.group_field_service_hide_price')
    group_field_service_allow_quotations = fields.Boolean(
        "Extra Quotations",
        implied_group='planning.group_field_service_allow_quotations',
        help="Create new quotations directly from interventions.",
    )
    group_field_service_allow_customer_ratings = fields.Boolean(
        string="Customer Ratings",
        implied_group='planning.group_field_service_allow_customer_ratings',
        help="Track customer satisfaction for interventions.",
    )
    field_service_travel_fees = fields.Boolean(related="company_id.field_service_travel_fees", readonly=False)
    group_field_service_allow_equipment = fields.Boolean(
        'Equipment',
        group='planning.group_planning_user',
        implied_group='planning.group_field_service_allow_equipment',
        help='Track customer equipment and intervention history',
    )

    def set_values(self):
        super().set_values()
        if self.website_planning_field_service and not self.module_website_planning_field_service:
            self.module_website_planning_field_service = True

        if not self.module_planning_field_service_stock and self.group_field_service_allow_equipment:
            self.module_planning_field_service_stock = True
