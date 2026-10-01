# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        printer_ids = data['pos.prep.display'].printer_ids
        return [('id', 'in', printer_ids.ids)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ['name', 'product_categories_ids', 'printer_ip', 'use_lna']

    @api.constrains('use_type')
    def _check_preparation_display_printer_type(self):
        # When changing the type of a printer already linked to a preparation display
        prep_printer_ids = self.filtered(lambda p: p.use_type != 'preparation').ids
        if self.env['pos.prep.display'].search_count([('printer_ids', 'in', prep_printer_ids)]):
            raise ValidationError(
                _("Printer type cannot be changed because it is linked to a preparation display.")
            )
