# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models
from . import wizard
from . import controller
from . import demo


def _post_init_hook(env):
    env['account.chart.template']._load_pre_defined_data({
        'account.account': {
            'depreciation_model_id',
            'asset_depreciation_account_id',
            'asset_expense_account_id',
        },
        'account.depreciation.model': {
            'method',
            'method_number',
            'method_period',
            'method_progress_factor',
            'company_id',
        },
    })
