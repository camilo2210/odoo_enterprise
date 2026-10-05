from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        # EXTENDS 'account'
        base_line = super()._prepare_product_base_line_for_taxes_computation(product_line)
        pos_config = self.pos_order_ids.config_id
        italian_printer = pos_config.receipt_printer_ids.filtered(lambda p: p.printer_type == 'it_fiscal_printer')
        base_line['l10n_it_epson_printer'] = self.country_code == 'IT' and italian_printer
        return base_line
