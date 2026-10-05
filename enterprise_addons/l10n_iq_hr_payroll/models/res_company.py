# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_iq_is_oil_and_gas_company = fields.Boolean(string="Is Oil and Gas Company")
    l10n_iq_annual_work_entry_type_id = fields.Many2one("hr.work.entry.type",
        string="IQ Annual Leave Time-off Type",
        default=lambda self: self.env.ref("hr_work_entry.iq_work_entry_type_legal_leave", raise_if_not_found=False))
