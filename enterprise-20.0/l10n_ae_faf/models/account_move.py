from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_ae_import_permit_number = fields.Char(string="Import Permit")
