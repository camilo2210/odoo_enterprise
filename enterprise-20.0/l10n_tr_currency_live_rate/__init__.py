from odoo.tools.sql import create_column

from . import models
from . import wizard


def _pre_init_hook(env):
    """Backfill the new stored fields, so existing rows keep their current behavior"""
    # l10n_tr_buy_rate: mirror the existing rate for old rows
    create_column(env.cr, "res_currency_rate", "l10n_tr_buy_rate", "numeric")
    env.cr.execute("UPDATE res_currency_rate SET l10n_tr_buy_rate = rate")

    # l10n_tr_currency_rate_type: 'sell' matches the single rate existing documents already used
    create_column(env.cr, "account_move", "l10n_tr_currency_rate_type", "varchar")
    env.cr.execute("UPDATE account_move SET l10n_tr_currency_rate_type = 'sell'")

    create_column(env.cr, "account_payment", "l10n_tr_currency_rate_type", "varchar")
    env.cr.execute("UPDATE account_payment SET l10n_tr_currency_rate_type = 'sell'")
