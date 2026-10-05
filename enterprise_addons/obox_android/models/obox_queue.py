from odoo import api, fields, models

_UNIQUE_ANDROID_ACTION_TYPES = ["screenshot", "logs", "open_kiosk", "kiosk_screen_lock", "kiosk_reload"]


class OboxQueue(models.TransientModel):
    _inherit = "obox.queue"

    action_type = fields.Selection(
        selection_add=[
            ("request_sync", "Request Sync"),
            ("screenshot", "Screenshot"),
            ("logs", "Fetch Logs"),
            ("open_kiosk", "Open Kiosk"),
            ("kiosk_screen_lock", "Lock / Unlock Screen"),
            ("kiosk_reload", "Reload Kiosk"),
        ],
        ondelete={
            "request_sync": "cascade",
            "screenshot": "cascade",
            "logs": "cascade",
            "open_kiosk": "cascade",
            "kiosk_screen_lock": "cascade",
            "kiosk_reload": "cascade",
        },
    )

    @api.model
    def _get_unique_action_types(self):
        return [*super()._get_unique_action_types(), *_UNIQUE_ANDROID_ACTION_TYPES]
