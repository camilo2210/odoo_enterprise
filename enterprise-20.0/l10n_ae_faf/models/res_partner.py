from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    l10n_ae_name_ar = fields.Char(
        string="Arabic Name",
        help="Fill in the Arabic name of the partner for the generation of the Federal Tax Authority (FTA) Audit File (FAF)"
    )
    l10n_ae_tax_agency_number = fields.Char(
        string="Tax Agency Number",
    )
