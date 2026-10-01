from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    esg_main_company_id = fields.Many2one(
        'res.company',
        domain=[('parent_id', '=', False)],
        config_parameter='esg.esg_main_company',
    )
    esg_fiscal_year_date_from = fields.Date('Fiscal Year Date From', compute='_compute_fiscal_year_dates')
    esg_fiscal_year_date_to = fields.Date('Fiscal Year Date To', compute='_compute_fiscal_year_dates')
    group_esg_csrd_reporting = fields.Boolean(implied_group='esg.group_esg_csrd_reporting')

    @api.depends('esg_main_company_id')
    def _compute_fiscal_year_dates(self):
        today = fields.Date.context_today(self)
        for config in self:
            if config.esg_main_company_id:
                fiscal_year_dates = config.esg_main_company_id.compute_fiscalyear_dates(today)
                config.esg_fiscal_year_date_from = fiscal_year_dates['date_from']
                config.esg_fiscal_year_date_to = fiscal_year_dates['date_to']
            else:
                config.esg_fiscal_year_date_from = False
                config.esg_fiscal_year_date_to = False
