# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    gofood_customer_id = fields.Char(
        string='GoFood Customer ID',
        help='The GoFood Customer ID used for the GoFood payment provider.'
    )
