from odoo import fields
from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class TestAccountAssetCommon(AccountTestInvoicingCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_asset_model_5_years = cls.env['account.depreciation.model'].create({
            'method': 'linear',
            'method_number': 5,
            'method_period': '12',
            'journal_id': cls.company_data['default_journal_misc'].id,
            'company_id': cls.env.company.id,
        })
        cls.company_data['default_account_assets'].depreciation_model_id = cls.account_asset_model_5_years
        cls.company_data['default_account_assets'].asset_depreciation_account_id = cls.company_data['default_account_assets'].copy()
        cls.company_data['default_account_assets'].asset_expense_account_id = cls.company_data['default_account_expense']

    @classmethod
    def create_asset(
        cls,
        *,
        value,
        method_number=None,
        method_period=None,
        method='linear',
        method_progress_factor=None,
        prorata_computation_type='none',
        import_depreciation=0,
        **asset_values,
    ):
        model_values = {
            'method': method,
        }
        if method != 'no_depreciation':
            model_values = {
                **model_values,
                'method_number': method_number,
                'method_period': method_period,
                'prorata_computation_type': prorata_computation_type,
            }
            if method_progress_factor is not None:
                model_values['method_progress_factor'] = method_progress_factor

        # Check asset model exists before creating a new one (due to constraint on uniqueness of asset models)
        asset_model = cls.env['account.depreciation.model'].search(
            [(field, '=', field_value) for field, field_value in model_values.items()],
            limit=1,
        )
        if not asset_model:
            asset_model = cls.env['account.depreciation.model'].create(model_values)

        return cls.env['account.asset'].create({
            'name': 'nice asset',
            'account_asset_id': cls.company_data['default_account_assets'].id,
            'acquisition_date': "2020-02-01",
            'original_value': value,
            'salvage_value': 0,
            'already_depreciated_amount_import': import_depreciation,
            'model_id': asset_model.id,
            **asset_values,
        })

    @classmethod
    def _get_depreciation_move_values(cls, date, depreciation_value, remaining_value, depreciated_value, state):
        return {
            'date': fields.Date.from_string(date),
            'depreciation_value': depreciation_value,
            'asset_remaining_value': remaining_value,
            'asset_depreciated_value': depreciated_value,
            'state': state,
        }
