# Part of Odoo. See LICENSE file for full copyright and licensing details.
from . import models


def post_init(env):
    # NCM codes are loaded from CSV, but the user should be able to update them.
    env['ir.model.data'].search([
        ('model', '=', 'l10n_br.ncm.code'),
        ('module', '=', 'l10n_br_avatax')
    ]).write({'noupdate': True})
