from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ae_tax_agency = fields.Many2one(comodel_name='res.partner', string="Tax Agency")
    l10n_ae_tax_agent = fields.Many2one(comodel_name='res.partner', string="Tax Agent")
    l10n_ae_name_ar = fields.Char(
        related='partner_id.l10n_ae_name_ar', readonly=False,
        help="Fill in the Arabic name of your company for the generation of the Federal Tax Authority (FTA) Audit File (FAF)",
    )
