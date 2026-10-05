from odoo import fields, models


class QualityCheck(models.Model):
    _inherit = "quality.check"

    obox_ip = fields.Char(related="point_id.obox_device_id.obox_id.local_address")
