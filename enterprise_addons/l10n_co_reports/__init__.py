# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizard
from . import report


def _post_init_hook(env):
    env['ir.model.data'].search([('model', '=', 'l10n_co.exogenous.category')]).write({'noupdate': True})
    env['ir.model.data'].search([('model', '=', 'l10n_co.exogenous.config')]).write({'noupdate': True})
