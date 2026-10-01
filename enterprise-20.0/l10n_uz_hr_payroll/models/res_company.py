# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_uz_social_tax_category = fields.Selection([
        ("taxpayer", "Taxpayers"),
        ("budgetary", "Budgetary Organizations"),
        ("sos", "Association 'SOS - Children's Villages of Uzbekistan'"),
        ("disability", "Taxpayers using the labor of persons with disabilities"),
    ], default="taxpayer", string="Uzbekistan Social Tax Category")
    l10n_uz_annual_leave_work_entry_type_id = fields.Many2one(
        "hr.work.entry.type",
        string="Uzbekistan Annual Leave Type",
        default=lambda self: self.env.ref("hr_work_entry.l10n_uz_work_entry_type_annual_labor_leave", raise_if_not_found=False),
    )
