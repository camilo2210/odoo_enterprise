# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee.public"

    l10n_hk_rentals_count = fields.Integer(compute='_compute_l10n_hk_rentals_count')

    def _compute_l10n_hk_rentals_count(self):
        self._compute_from_employee('l10n_hk_rentals_count')

    def l10n_hk_action_open_rentals(self):
        self.ensure_one()
        if not self.is_user:
            return None
        return self.employee_id.action_open_rentals()
