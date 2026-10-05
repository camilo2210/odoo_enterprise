from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template(template='in', model='account.asset.group', demo=True)
    def _l10n_in_get_demo_data_1_asset_group(self):
        return {
            'l10n_in_asset_group_demo': {
                'name': self.env._("Computer and Laptop"),
            },
        }

    @template(template='in', model='account.depreciation.model', demo=True)
    def _l10n_in_get_demo_data_2_depreciation_model(self):
        return {
            'l10n_in_depreciation_model_demo': {
                'method': 'linear',
                'method_number': 5,
                'method_period': '12',
                'company_id': self.env.company.id,
            },
        }

    @template(template='in', model='account.account', demo=True)
    def _l10n_in_get_demo_data_3_asset_account(self):
        return {
            'p1015': {
                'depreciation_model_id': 'l10n_in_depreciation_model_demo',
                'asset_depreciation_account_id': 'p1015',
                'asset_expense_account_id': 'p213300',
            },
        }

    @template(template='in', model='account.asset', demo=True)
    def _l10n_in_get_demo_data_4_asset(self):
        return {
            'l10n_in_asset_model_demo': {
                'name': self.env._("Laptop"),
                'original_value': 100000,
                'account_asset_id': 'p1015',
                'asset_group_id': 'l10n_in_asset_group_demo',
                'model_id': 'l10n_in_depreciation_model_demo',
            },
        }
