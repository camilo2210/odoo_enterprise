
from odoo import fields, models


class BiometricEvent(models.Model):
    _inherit = "hr.attendance.biometric.event"

    provider = fields.Selection(
        selection_add=[("essl", "eSSL")], ondelete={"essl": "cascade"},
    )
