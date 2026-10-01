# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    l10n_sa_bank_establishment_code = fields.Char("Establishment Code")
