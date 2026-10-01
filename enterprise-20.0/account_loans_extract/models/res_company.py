from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    extract_loan_digitalization_mode = fields.Selection(
        selection=[
            ('no_send', "Do not digitize"),
            ('auto_send', "Digitize automatically"),
        ],
        string="Digitization mode on loans",
        default='auto_send')
