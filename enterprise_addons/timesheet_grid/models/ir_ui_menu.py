from odoo import models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if self.env.company.timesheet_encode_uom_id == self.env.ref("uom.product_uom_day"):
            res.extend(
                [
                    self.env.ref("timesheet_grid.menu_activitywatch_sync").id,
                    self.env.ref("timesheet_grid.hr_timesheet_menu_configuration_assistant").id,
                ],
            )
        if self.env.user.has_group('timesheet_grid.group_timesheet_assistant'):
            res.append(self.env.ref('hr_timesheet.hr_timesheet_menu_configuration').id)
        return res
