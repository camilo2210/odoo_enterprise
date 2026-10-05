from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # at the moment it's not mandatory but will be in the future
    iso20022_lei = fields.Char(
        string='LEI',
        help='Legal Entity Identifier',
        compute='_compute_iso20022_lei',
        inverse='_inverse_iso20022_lei',
    )

    @api.depends('additional_identifiers')
    def _compute_iso20022_lei(self):
        for partner in self:
            partner.iso20022_lei = partner._get_additional_identifier('LEI')

    def _inverse_iso20022_lei(self):
        for partner in self:
            partner._set_additional_identifier('LEI', partner.iso20022_lei)
