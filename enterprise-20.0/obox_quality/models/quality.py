from odoo import fields, models


class QualityPoint(models.Model):
    _inherit = "quality.point"

    obox_device_id = fields.Many2one(
        "obox.device",
        ondelete="restrict",
        domain=lambda self: [("type", "in", ["scale", "camera"])],
        index='btree_not_null',
    )


class QualityCheck(models.Model):
    _inherit = "quality.check"

    obox_device_identifier = fields.Char("Obox device identifier", related="point_id.obox_device_id.identifier")
    obox_ip = fields.Char(related="point_id.obox_device_id.obox_id.local_ip")
