from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    timesheet_product_id = fields.Many2one(
        'product.product', string='Service to Bill',
        groups="hr.group_hr_user",
        domain="""[
            ('type', '=', 'service'),
            ('invoice_policy', '=', 'delivery'),
            ('service_type', '=', 'timesheet'),
        ]""",
        help="Service billed based on the employee’s time spent on the field service intervention. "
             "If none is selected, the system will use the service from the selected sales order or create one automatically.",
    )
