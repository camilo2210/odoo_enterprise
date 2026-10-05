from odoo import fields, models


class QualityCheckWizard(models.TransientModel):
    _inherit = "quality.check.wizard"

    obox_device_identifier = fields.Char("Obox Device", related="current_check_id.point_id.obox_device_id.identifier", store=False)
    obox_ip = fields.Char(related="current_check_id.point_id.obox_device_id.obox_id.local_ip", store=False)
