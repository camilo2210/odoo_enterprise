from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = 'account.chart.template'

    @template(model='account.depreciation.model')
    def _get_account_asset(self, template_code):
        all_company_models = self.env['account.depreciation.model'].search([('company_id', '=', False)])
        existing_models = {
            tuple(model[field] for field in ['method', 'method_number', 'method_period']): model
            for model in all_company_models
        }

        company_models = {}
        for xmlid, vals in self._parse_csv(template_code, 'account.depreciation.model').items():
            model_key = (vals['method'], int(vals['method_number']), vals['method_period'])
            # If company model already exists as an all companies model,
            # reuse them instead of creating new ones by using their xmlid to reference existing model
            if model_key in existing_models:
                self.env['ir.model.data']._update_xmlids([{
                    'xml_id': self.company_xmlid(xmlid, self.env.company),
                    'record': existing_models[model_key],
                    'noupdate': True,
                }])
            else:
                company_models[xmlid] = {
                    **vals,
                    'company_id': self.env.company.id,
                }
        return company_models

    def _get_template_models(self):
        template_models = super()._get_template_models()
        return template_models + ('account.asset',)
