from odoo import SUPERUSER_ID, api
from odoo.addons.l10n_pe_edi.hooks import _activate_sunat_unspsc_codes


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _activate_sunat_unspsc_codes(env)
