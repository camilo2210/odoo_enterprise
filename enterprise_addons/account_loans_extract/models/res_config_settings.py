from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    extract_loan_digitalization_mode = fields.Selection(
        related='company_id.extract_loan_digitalization_mode',
        string='Loans',
        readonly=False,
    )
