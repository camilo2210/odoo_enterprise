from odoo import models, fields


class L10nFRResPartnerProfession(models.Model):
    _name = 'l10n_fr.res.partner.profession'
    _description = 'Profession for French partners'

    name = fields.Char(string='Profession', required=True, translate=True)
