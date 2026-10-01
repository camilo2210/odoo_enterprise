from odoo import fields, models


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    marketing_activity_ids = fields.One2many("marketing.activity", "server_action_id")
