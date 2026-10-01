# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_us_signatory_id = fields.Many2one(
        "hr.employee",
        string="Signatory",
        help="Signatory used in forms 940 and 941. Name, title and phone number will be shared."
    )
    l10n_us_business_structure = fields.Selection(
        [
            ("s_corp", "S Corporation or LLC as S Corp"),
            ("partnership", "Partnership or LLC as Partnership"),
            ("c_corp", "C Corporation or LLC as C Corp"),
            ("sole_proprietor", "Sole Proprietor or Single member LLC"),
            ("trust", "Trust or Estate"),
            ("exempt", "Exempt Organization"),
            ("government", "State and Local Governmental Employer"),
        ],
        string="Business Structure",
        help="Select the appropriate classification of your business. These will be used in forms 940 and 941.",
    )
    l10n_us_state_identifier = fields.Char(
        string="State ID",
        help="State identifier used in W2 forms.",
    )
