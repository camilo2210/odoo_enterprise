# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    l10n_sa_saudization_minimum_wage = fields.Float(
        string="Minimum Wage",
        help="Minimum wage for Saudi employees to be considered in the Saudization rate calculation."
    )
