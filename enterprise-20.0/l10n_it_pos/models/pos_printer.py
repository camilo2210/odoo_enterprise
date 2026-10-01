# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PosPrinter(models.Model):
    _inherit = 'pos.printer'

    printer_type = fields.Selection(
        selection_add=[('it_fiscal_printer', 'Italian Fiscal Printer')],
        ondelete={'iot': 'set default'}
    )

    @api.constrains('printer_type', 'use_type')
    def _check_printer_types(self):
        for record in self:
            if record.printer_type == 'it_fiscal_printer' and record.use_type == 'preparation':
                raise ValidationError(_('A fiscal printer cannot be set to preparation type.'))

    @api.constrains('printer_ip')
    def _constrains_printer_ip(self):
        for record in self:
            if record.printer_type == 'it_fiscal_printer' and not record.printer_ip:
                raise ValidationError(_("Printer IP Address cannot be empty."))
