from odoo import models, fields


class Printer(models.Model):
    _inherit = "printer.printer"

    type = fields.Selection(selection_add=[("iot", "IoT")], ondelete={"iot": "set default"})
    iot_device_id = fields.Many2one(
        "iot.device",
        string="IoT Printer",
        ondelete="cascade",
        index="btree_not_null",
        domain="[('type', '=', 'printer')]",
    )
