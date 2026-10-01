# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_sa_late_employee_grace = fields.Integer(related='company_id.l10n_sa_late_employee_grace', readonly=False)
