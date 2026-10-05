# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_bg_saft_related_company_ids = fields.Many2many(
        comodel_name='res.company',
        relation='l10n_bg_saft_relations',
        string='Related companies (BG SAF-T)',
        help='All the related companies according to §1, item 3 of the DR of DOPK. This is used for SAF-T report export.',
    )

    def _get_all_additional_identifiers_metadata(self):
        # OVERRIDE base/models/res_partner

        additional_identifiers_metadata = super()._get_all_additional_identifiers_metadata()
        additional_identifiers_metadata['BG_CN'] = {
            'label': _lt('Citizen Identification'),
            'help': _lt('Bulgarian national identification number'),
            'placeholder': '8001014556',
            'countries': ['BG'],
        }

        return additional_identifiers_metadata
