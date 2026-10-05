# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_bg_saft_tax_accounting_basis = fields.Selection(
        [
            ('A', 'A: for commercial enterprises'),
            ('BANK', 'BANK: for credit institutions and non-bank financial institutions'),
            ('INSURANCE', 'INSURANCE: for insurance companies'),
            ('P', 'P: for budget enterprises'),
        ],
        string='Tax Accounting Basis (BG)',
    )

    l10n_bg_saft_tax_entity_type = fields.Selection(
        [
            ('Company', 'Company'),
            ('Division', 'Division'),
            ('Branch', 'Branch'),
        ],
        string='Entity Type (BG)',
        default='Company',
    )

    l10n_bg_saft_ownership_structure = fields.Selection(
        [
            ('1', '1 - Local group headquarters'),
            ('2', '2 - Headquarters of a multinational group'),
            ('3', '3 - Part of a local group'),
            ('4', '4 - Part of a multinational group'),
            ('5', '5 - No'),
        ],
        string='Onwership Structure (BG)',
        help='Indicates whether the obligee is part of a group or not',
    )

    l10n_bg_saft_related_partner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='l10n_bg_saft_relations',
        string='Related partners (BG SAF-T)',
        help='All the related partners according to §1, item 3 of the DR of DOPK. '
            'This is used for SAF-T report export.',
    )

    l10n_bg_saft_ultimate_owner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation="l10n_bg_saft_company_ultimate_owners_rel",
        domain="[('is_company','=','True'),('id','!=',partner_id)]",
        string='Ultimate owners (BG SAF-T)',
        help='The ultimate owners when part of a local or multinational group. '
            'This is used for the SAF-T report export. The final parent company is determined '
            'according to the accounting standards applicable by the filer. If the '
            'final establishment is more than one, data shall be submitted for all '
            'final establishments.',
    )

    l10n_bg_saft_beneficial_owner_ids = fields.Many2many(
        comodel_name='res.partner',
        relation="l10n_bg_saft_company_beneficial_owners_rel",
        domain="[('is_company','=','False')]",
        string='Beneficial owners (BG SAF-T)',
        help="The beneficial owner of the company is determined under the Anti-Money "
            "Laundering Act. If there is more than one beneficial owner, data for all "
            "beneficial owners shall be submitted. "
            "This is used for the SAF-T report export.",
    )
