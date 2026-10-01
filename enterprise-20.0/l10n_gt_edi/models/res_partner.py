from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_gt_edi_phrase_ids = fields.Many2many(
        comodel_name="l10n_gt_edi.phrase",
        string="Phrases",
    )
    l10n_gt_edi_consignatory_code = fields.Char(
        string="Consignatory Code",
        size=17,
    )
