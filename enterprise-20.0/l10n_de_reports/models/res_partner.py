# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.business_data import split_vat


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_de_datev_identifier = fields.Integer(
        string='DateV Vendor',
        copy=False,
        tracking=True,
        company_dependent=True,
        index='btree_not_null',
        help="In the DateV export of the General Ledger, each vendor will be identified by this identifier. "
        "If this identifier is not set, the database id of the partner will be added to a multiple of ten starting by the number 7."
        "The account code's length can be specified in the company settings."
    )
    l10n_de_datev_identifier_customer = fields.Integer(
        string='DateV Customer',
        copy=False,
        tracking=True,
        company_dependent=True,
        index='btree_not_null',
        help="In the DateV export of the General Ledger, each customer will be identified by this identifier. "
        "If this identifier is not set, the database id of the partner will be added to a multiple of ten starting by the number 1."
        "The account code's length can be specified in the company settings."
    )

    def _compute_is_company(self):
        """Check if the given VAT corresponds to a German company.

        True if VAT matches German company format, False otherwise.
        """
        l10n_de_partners = self.filtered(lambda p: p.country_code == 'DE')
        for partner in l10n_de_partners:
            partner.is_company = False
            if partner.has_vat:
                vat_country, vat_number = split_vat(partner.vat)
                # German VAT IDs always start with 'DE' + 9 digits
                # A partner is considered as a company if they are their own commercial entity
                if vat_country == 'DE' and len(vat_number) == 9 and vat_number.isdigit() and partner.commercial_partner_id == partner:
                    partner.is_company = True

        super(ResPartner, self - l10n_de_partners)._compute_is_company()

    @api.constrains('l10n_de_datev_identifier')
    def _check_datev_identifier(self):
        partners = self.filtered('l10n_de_datev_identifier')
        identifiers = partners.mapped('l10n_de_datev_identifier')
        if not len(partners) == len(set(identifiers)) == self.with_context(active_test=False).search_count(
                [('l10n_de_datev_identifier', 'in', identifiers)], limit=len(identifiers) + 1):
            raise ValidationError(_('You have already defined a partner with the same Datev identifier. '))

    @api.constrains('l10n_de_datev_identifier_customer')
    def _check_datev_identifier_customer(self):
        partners = self.filtered('l10n_de_datev_identifier_customer')
        identifiers = partners.mapped('l10n_de_datev_identifier_customer')
        if not len(partners) == len(set(identifiers)) == self.with_context(active_test=False).search_count(
                [('l10n_de_datev_identifier_customer', 'in', identifiers)], limit=len(identifiers) + 1):
            raise ValidationError(_('You have already defined a partner with the same Datev Customer identifier'))
