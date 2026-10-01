from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    field_service_travel_fees_mode = fields.Selection(
        selection=[
            ('fixed', "Fixed Fee"),
            ('distance', "Fee per Distance"),
        ],
        string="Travel Fees Mode",
        default='fixed',
        required=True,
    )
    travel_time_invoicing_product_id = fields.Many2one("product.template",
        domain=[
            ('type', '=', 'service'),
            '|',
                '&',
                    ('service_type', '=', 'manual'),
                    ('invoice_policy', '=', 'delivery'),
                '&',
                    ('service_type', '=', 'timesheet'),
                    ('invoice_policy', '=', 'order'),
            ('sale_ok', '=', True),
        ],
        default=lambda self: self.env.ref('planning_field_service_sale_timesheet.field_service_product_travel_invoice', raise_if_not_found=False))
    planning_project_id = fields.Many2one(
        'project.project',
        string="Project",
        compute='_compute_planning_project_id',
        store=True,
        readonly=False,
        default=lambda self: self.env.ref('planning_field_service_sale_timesheet.fsm_project', raise_if_not_found=False),
        domain=[('allow_billable', '=', True), ('allow_timesheets', '=', True)],
        help="Select a project to generate timesheets and invoice your time.",
    )

    @api.depends('planning_project_id.allow_billable', 'planning_project_id.allow_timesheets', 'planning_project_id.company_id')
    def _compute_planning_project_id(self):
        for company in self:
            project = company.planning_project_id
            if not (project.allow_billable or project.allow_timesheets or project.company_id != company):
                company.planning_project_id = False
