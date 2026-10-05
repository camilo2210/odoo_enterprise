from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_eg_annual_work_entry_type_id = fields.Many2one(
        'hr.work.entry.type', string="Annual Leave Time-off Type",
        domain="[('id', 'in', allowed_work_entry_type_ids)]",
        default=lambda self: self.env.ref('hr_work_entry.eg_work_entry_type_legal_leave', raise_if_not_found=False))
    l10n_eg_nosi_code = fields.Char(string='Company NOSI Code')
