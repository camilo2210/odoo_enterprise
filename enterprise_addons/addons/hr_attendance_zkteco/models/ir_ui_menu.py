from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    @api.model
    def _load_menus_blacklist(self):
        blacklist = super()._load_menus_blacklist()
        if self.env.user.company_ids.filtered("zkteco_initial_sync_done"):
            return blacklist

        for xmlid in (
            "hr_attendance_zkteco.zkteco_transactions_menu",
            "hr_attendance_zkteco.zkteco_terminal_menu",
        ):
            if menu := self.env.ref(xmlid, raise_if_not_found=False):
                blacklist.append(menu.id)

        return blacklist
