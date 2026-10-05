# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_sa_late_employee_grace = fields.Integer(string="Grace Period In Favor Of Employee", default=0)
