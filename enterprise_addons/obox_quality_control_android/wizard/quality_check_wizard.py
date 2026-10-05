from odoo import fields, models


class QualityCheckWizard(models.TransientModel):
    _inherit = "quality.check.wizard"

    obox_ip = fields.Char(related="current_check_id.point_id.obox_device_id.obox_id.local_address", store=False)
