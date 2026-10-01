# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class PackageType(models.Model):
    _inherit = 'stock.package.type'

    package_carrier_type = fields.Selection(selection_add=[('usps_rest', 'USPS')])

    @api.depends('package_carrier_type')
    def _compute_length_uom_name(self):
        """
        Keep default length_uom and then convert it later down the line
        """
        super()._compute_length_uom_name()
        uom_name = self.env['product.template']._get_length_uom_name_from_ir_config_parameter()
        for package in self:
            if package.package_carrier_type == 'usps_rest':
                package.length_uom_name = uom_name
