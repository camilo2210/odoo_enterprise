from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        group_timesheet_assistant = self.env.user.has_group('timesheet_grid.group_timesheet_assistant')
        is_uom_day = self.env.company.timesheet_encode_uom_id == self.env.ref("uom.product_uom_day")
        if not any(company.timesheet_show_rates for company in self.env.user.company_ids):
            group_timesheet_manager = self.env.user.has_group('hr_timesheet.group_timesheet_manager')
            # Hide the Configuration menu when the user cannot access any of the features configured from it.
            # Assistant users can access it only when Assistant Rules are available (UoM != Days), while Billing Target
            # settings are restricted to All Timesheet and Administrators rights.
            if not (group_timesheet_assistant and (
                not is_uom_day
                or group_timesheet_manager
                or self.env.user.has_group('base.group_system')
                or self.env.user.has_group('base.group_no_one')
            )):
                res.append(self.env.ref('timesheet_grid.hr_timesheet_enterprise_menu_configuration').id)
            else:
                res.append(self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_employee_configuration').id)
        else:
            if not group_timesheet_assistant:
                res.append(self.env.ref('hr_timesheet.hr_timesheet_menu_configuration').id)
            if self.env.user.has_group('hr.group_hr_user'):
                res.append(self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_employee_billable_time_target').id)
            # When Assistant Rules are unavailable (UoM = Days), the Configuration menu only provides access to billing-related settings.
            # Hide it for users who do not have All Timesheet or Administration rights.
            if group_timesheet_assistant and is_uom_day and not (
                self.env.user.has_group('hr_timesheet.group_hr_timesheet_approver')
                or self.env.user.has_group('base.group_system')
                or self.env.user.has_group('base.group_no_one')
            ):
                res.append(self.env.ref('timesheet_grid.hr_timesheet_enterprise_menu_configuration').id)
        if not self.env.company.timesheet_show_leaderboard:
            res.append(self.env.ref('sale_timesheet_enterprise.hr_timesheet_menu_configuration_tips').id)

        return res
