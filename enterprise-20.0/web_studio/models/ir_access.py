# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrAccess(models.Model):
    _name = 'ir.access'
    _description = 'Rule'
    _inherit = ['studio.mixin', 'ir.access']
