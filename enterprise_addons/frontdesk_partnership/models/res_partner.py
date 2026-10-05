# Part of Odoo. See LICENSE file for full copyright and licensing details.

from random import choice
from string import digits

from odoo import api, models, fields


class ResPartner(models.Model):
    _name = 'res.partner'
    _inherit = ['res.partner']

    last_barcode_scan = fields.Datetime("Barcode Last Frontdesk Scanned Time", readonly=True)

    def generate_barcode(self):
        for record in self:
            if record.grade_id and not record.barcode:
                record.write({'barcode': '042' + "".join(choice(digits) for i in range(9))})

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.generate_barcode()
        return res

    def write(self, vals):
        res = super().write(vals)
        if vals.get('grade_id') and 'barcode' not in vals:
            self.generate_barcode()
        return res
