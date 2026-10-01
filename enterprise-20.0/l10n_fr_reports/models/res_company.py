# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_fr_rof_type = fields.Integer(
        string="ROF",
        default=1,
        help="Tax obligation reference",
    )
    l10n_fr_das2_activity = fields.Char(
        string="Activity",
        help="The company's main activity. Used in the DAS2 report",
    )
    l10n_fr_fiscal_regime = fields.Selection(  # TODO: repalce l10n_fr_pdp_periodicity with this and account_return_periodicity
        selection=[
            ('simplified', 'Simplified'),
            ('normal', 'Normal'),
        ],
        default='simplified',
        required=True,
    )
    l10n_fr_aspone_sso_client_id = fields.Char()

    def _get_countries_allowing_tax_representative(self):
        rslt = super()._get_countries_allowing_tax_representative()
        rslt.add(self.env.ref('base.fr').code)
        return rslt
