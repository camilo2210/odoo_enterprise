from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_be_soda_use_analytic = fields.Boolean(string="Analytic Mapping")
    l10n_be_soda_analytic_plan = fields.Many2one(string="Analytic Plan", comodel_name='account.analytic.plan')
