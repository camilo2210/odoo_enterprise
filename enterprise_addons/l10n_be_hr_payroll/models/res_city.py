from odoo import fields, models


class ResCity(models.Model):
    _inherit = 'res.city'

    l10n_be_nis_code = fields.Char('NIS Code', size=5)
    l10n_be_language = fields.Char('Language')
