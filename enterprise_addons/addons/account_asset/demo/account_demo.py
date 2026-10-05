from odoo import models
from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template('generic_coa', model='account.asset.group', demo=True)
    def _get_demo_data_1_asset_group(self):
        return {
            'account_asset_group_demo': {
                'name': self.env._("Odoo Office"),
            },
        }

    @template('generic_coa', model='account.depreciation.model', demo=True)
    def _get_demo_data_2_depreciation_model(self):
        return {
            'account_depreciation_model_demo': {
                'display_name': self.env._("Demo Depreciation Model"),
                'method': 'linear',
                'method_number': 2,
                'method_period': '12',
                'company_id': self.env.company.id,
            },
        }

    @template('generic_coa', model='account.account', demo=True)
    def _get_demo_data_3_asset_account(self):
        return {
            'fixed_assets': {
                'depreciation_model_id': 'account_depreciation_model_demo',
                'asset_depreciation_account_id': 'fixed_assets',
                'asset_expense_account_id': 'expense',
            },
        }

    @template('generic_coa', model='account.asset', demo=True)
    def _get_demo_data_4_asset(self):
        return {
            'account_asset_model_demo': {
                'name': self.env._("Demo Asset"),
                'prorata_computation_type': 'none',
                'original_value': 1000,
                'account_asset_id': 'fixed_assets',
                'asset_group_id': 'account_asset_group_demo',
                'model_id': 'account_depreciation_model_demo',
            },
        }
