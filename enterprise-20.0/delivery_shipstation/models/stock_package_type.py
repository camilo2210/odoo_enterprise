# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class StockPackageType(models.Model):
    _inherit = 'stock.package.type'

    package_carrier_type = fields.Selection(selection_add=[('shipstation', 'ShipStation')])
    shipstation_carrier_code = fields.Char('ShipStation Carrier Code', readonly=True)

    @api.depends('package_carrier_type')
    def _compute_length_uom_name(self):
        """ShipStation converts dimensions to inches in the API request,
        so display the company's configured length UOM instead of forcing inches."""
        uom_name = self.env['product.template']._get_length_uom_name_from_ir_config_parameter()
        shipstation_package_types = self.filtered(lambda pt: pt.package_carrier_type == 'shipstation')
        for package in shipstation_package_types:
            package.length_uom_name = uom_name
        super(StockPackageType, self - shipstation_package_types)._compute_length_uom_name()
