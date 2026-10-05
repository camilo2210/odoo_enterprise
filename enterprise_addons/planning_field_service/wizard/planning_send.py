from odoo import models


class PlanningSend(models.TransientModel):
    _inherit = "planning.send"

    def action_send(self):
        notification = super().action_send()

        if (
            notification
            and notification.get("tag", "") == "display_notification"
            and notification["params"]["type"] == "success"
            and (slots_with_customer := self.slot_ids.filtered("partner_id"))
        ):
            slots_with_customer._send_intervention_scheduled()
        return notification
