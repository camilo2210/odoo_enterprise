from odoo import models


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    def _prepare_base_lines_for_taxes_computation(self):
        # OVERRIDE 'point_of_sale'
        base_lines = super()._prepare_base_lines_for_taxes_computation()
        for index, line in enumerate(self):
            country_code = line.company_id.account_fiscal_country_id.code
            config = line.order_id.config_id
            italian_printer = config.receipt_printer_ids.filtered(lambda p: p.printer_type == 'it_fiscal_printer')
            line_base_line = base_lines[index]
            line_base_line['l10n_it_epson_printer'] = country_code == 'IT' and italian_printer
        return base_lines
