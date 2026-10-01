# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from . import models
from . import wizard


_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    # UNSPSC category codes can be used in Kenya.
    env['product.unspsc.code'].flush_model()
    env.cr.execute('''
        UPDATE product_unspsc_code
           SET active = 'true'
         WHERE code ILIKE '%00'
    ''')
    env['product.unspsc.code'].invalidate_model()

    # Change all OSCU codes ir.model.data to noupdate, so it only gets updated through the cron
    xmls = env['ir.model.data'].search([('model', '=', 'l10n_ke_edi_oscu.code')])
    xmls.write({'noupdate': True})
