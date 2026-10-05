# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_jo_annual_work_entry_type_id = fields.Many2one("hr.work.entry.type",
        string="JO Annual Leave Time-off Type",
        domain="[('id', 'in', allowed_work_entry_type_ids)]",
        default=lambda self: self.env.ref("hr_work_entry.jo_work_entry_type_legal_leave", raise_if_not_found=False))
