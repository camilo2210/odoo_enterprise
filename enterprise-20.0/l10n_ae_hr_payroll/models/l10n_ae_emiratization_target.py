from odoo import fields, models


class L10nAeEmiratizationTarget(models.Model):
    _name = 'l10n_ae.emiratization.target'
    _description = 'Emiratization Target'

    effective_date = fields.Date(required=True)
    target_percentage = fields.Float(string="Target %", required=True)

    _target_percentage_range = models.Constraint(
        'CHECK(target_percentage >= 0 AND target_percentage <= 1)',
        'Target percentage must be between 0 and 1.',
    )
