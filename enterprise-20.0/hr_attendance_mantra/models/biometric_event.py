
from odoo import fields, models


class BiometricEvent(models.Model):
    _inherit = "hr.attendance.biometric.event"

    provider = fields.Selection(
        selection_add=[("mantra", "Mantra")], ondelete={"mantra": "cascade"},
    )
    transaction_id = fields.Char("Transaction ID")
