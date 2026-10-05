from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    l10n_uk_hmrc_vat_token = fields.Char(related='company_id.l10n_uk_hmrc_vat_token')
