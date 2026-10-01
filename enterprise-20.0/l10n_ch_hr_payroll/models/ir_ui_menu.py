# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        user_swiss_companies = self.env.user.company_ids.filtered(lambda c: c.country_code == 'CH')
        # only remove the menus when the user has just CH compnaies
        if user_swiss_companies and user_swiss_companies == self.env.user.company_ids:
            res.append(self.env.ref('hr_payroll.menu_hr_work_entry_type_view').id)
            res.append(self.env.ref('hr_payroll.hr_menu_salary_attachments').id)
        return res
