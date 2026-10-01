from odoo import fields, models


class L10n_LatamDocumentType(models.Model):
    _inherit = 'l10n_latam.document.type'

    l10n_do_edi_property_document_range_id = fields.Many2one(
        comodel_name='l10n_do_edi.document.type.range',
        string='Dominican Republic Authorized Range',
        company_dependent=True,
    )
