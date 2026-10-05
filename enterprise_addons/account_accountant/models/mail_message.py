from odoo import fields, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    message_type = fields.Selection(
        selection_add=[('transaction_details', "Transaction Details")],
        ondelete={'transaction_details': lambda recs: recs.write({'message_type': 'comment'})},
    )
