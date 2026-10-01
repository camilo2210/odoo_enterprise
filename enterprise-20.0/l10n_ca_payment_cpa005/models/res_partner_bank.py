# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re

from odoo import models, fields, api
from odoo.addons.base.models.res_partner_bank import sanitize_account_number
from odoo.exceptions import ValidationError


def cpa005_sanitize_account_number(account_number):
    """ CPA005 expects an `account_number` made of 12 digits at most.
    Strips separators and unwanted characters.
    Return an empty string when it doesn't have a valid format, even after normalization.
    """
    sanitized = sanitize_account_number(account_number) or ''
    return sanitized if re.fullmatch(r'[0-9]{1,12}', sanitized) else ''


def cpa005_sanitize_financial_institution_nr(fin_inst_nr):
    """ 9 digits """
    normalized = re.sub(r'\D+', '', fin_inst_nr or '')
    return normalized if re.fullmatch(r'[0-9]{9}', normalized) else ''


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    l10n_ca_financial_institution_number = fields.Char(
        "Financial Institution ID Number",
        size=9,
        help="9-digit number that identifies the financial institution where the vendor holds an account. It typically "
        "starts with a 0, followed by a 3-digit institution number or ID, and a 5-digit branch routing number. This is a "
        "mandatory field for Canadian EFT file generation.",
    )
    l10n_ca_cpa005_institution_number = fields.Char(compute='_compute_l10n_ca_cpa005_fi_number_parts')
    l10n_ca_cpa005_transit_number = fields.Char(compute='_compute_l10n_ca_cpa005_fi_number_parts')

    @api.constrains("l10n_ca_financial_institution_number")
    def _check_l10n_ca_cpa005_financial_institution_number(self):
        for bank in self:
            financial_institution_number = bank.l10n_ca_financial_institution_number
            if financial_institution_number and not cpa005_sanitize_financial_institution_nr(financial_institution_number):
                raise ValidationError(
                    self.env._(
                        'The Financial Institution ID Number of the "%s" bank account must be a 9 digit number. The '
                        "format is a 0, followed by a 3-digit institution number, and a 5-digit branch routing number.",
                        bank.display_name,
                    )
                )

    @api.depends('l10n_ca_financial_institution_number')
    def _compute_l10n_ca_cpa005_fi_number_parts(self):
        for bank in self:
            if fin_inst_nr := cpa005_sanitize_financial_institution_nr(bank.l10n_ca_financial_institution_number):
                bank.l10n_ca_cpa005_institution_number = fin_inst_nr[1:4]
                bank.l10n_ca_cpa005_transit_number = fin_inst_nr[4:9]
            else:
                bank.l10n_ca_cpa005_institution_number = False
                bank.l10n_ca_cpa005_transit_number = False
