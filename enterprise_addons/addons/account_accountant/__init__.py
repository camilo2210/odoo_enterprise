# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import demo
from . import models
from . import wizard

from odoo import Command

import logging

_logger = logging.getLogger(__name__)


def _account_accountant_post_init(env):
    company = env.company
    if company.country_id and 'SEPA' in company.country_id.country_group_codes:
        module_ids = env['ir.module.module'].search([
            ('name', 'in', ['account_iso20022', 'account_bank_statement_import_camt']),
            ('state', '=', 'uninstalled')
        ])
        if module_ids:
            module_ids.sudo().button_install()

    env['account.chart.template']._load_pre_defined_data({
        'res.company': {
            'deferred_expense_journal_id',
            'deferred_revenue_journal_id',
            'deferred_expense_account_id',
            'deferred_revenue_account_id',
        },
    })


def uninstall_hook(env):
    # Disable the basic group to remove access menus defined in account
    group_basic = env.ref('account.group_account_basic')
    group_manager = env.ref('account.group_account_manager')
    if group_basic:
        group_basic.write({
            'user_ids': [Command.clear()],
        })
        group_manager.write({
            'implied_ids': [Command.unlink(group_basic.id)],
        })
