# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools.misc import formatLang
from odoo.addons.l10n_eu_iot_scale_cert.controllers.checksum import calculate_scale_checksum
from odoo.addons.l10n_eu_iot_scale_cert.controllers.expected_checksum import EXPECTED_CHECKSUM


class PosOrderReceipt(models.AbstractModel):
    _inherit = 'pos.order.receipt'
    _description = 'Point of Sale Order Receipt Generator'

    def order_receipt_generate_data(self, basic_receipt=False):
        data = super().order_receipt_generate_data(basic_receipt)
        is_eu_country = self.company_id.country_id in self.env.ref('base.europe').country_ids
        l10n_eu_iot_scale_cert = is_eu_country and self.config_id.iot_scale_id and any(self.lines.mapped('product_id.to_weight'))
        if l10n_eu_iot_scale_cert:
            data['conditions']['l10n_eu_iot_scale_cert_show_warning'] = bool(calculate_scale_checksum()[0] != EXPECTED_CHECKSUM)

        return data

    def _order_receipt_generate_line_data(self):
        lines = super()._order_receipt_generate_line_data()
        digits = self.env['decimal.precision'].precision_get('Product Unit')
        for line_data, line_record in zip(lines, self.lines):
            line_data['show_uom'] = line_record.product_id.uom_id.id != self.env.ref('uom.product_uom_unit').id
            line_data['qty_full_precision'] = formatLang(self.env, line_data['qty'], digits) if line_data['show_uom'] else str(line_data['qty'])
        return lines
