# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    documents_hr_payroll_group_id = fields.Many2one(
        'res.group.functional', related='company_id.documents_hr_payroll_group_id', readonly=False)
