# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class IrQweb(models.AbstractModel):
    _inherit = "ir.qweb"

    def _get_bundles_to_pregenarate(self):
        js_assets, css_assets, bin_assets = super()._get_bundles_to_pregenarate()
        assets = {"voip.assets_sip_demo"}
        return (js_assets | assets, css_assets | assets, bin_assets)
