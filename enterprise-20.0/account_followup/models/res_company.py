from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    automatic_invoice_reminder = fields.Boolean(string="Automatic Invoice Reminders")
