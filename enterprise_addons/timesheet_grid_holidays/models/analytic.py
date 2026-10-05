# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, _
from odoo.fields import Domain
from odoo.exceptions import RedirectWarning, UserError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    def action_merge_timesheets(self):
        if self.holiday_id:
            if not self.env.user.has_group('hr_holidays.group_hr_holidays_user') and self.env.user not in self.holiday_id.sudo().user_id:
                raise UserError(_('You cannot merge timesheets that are linked to time off requests. Please use the Time Off application to modify or cancel your time off requests instead.'))
            warning_msg = _('You cannot merge timesheets that are linked to time off requests. Please use the Time Off application to modify or cancel your time off requests instead.')
            action = self._get_redirect_action()
            raise RedirectWarning(warning_msg, action, _('View Time Off'))
        return super().action_merge_timesheets()

    @api.model
    def grid_update_cell(self, domain, measure_field_name, value):
        return super().grid_update_cell(
            Domain.AND([domain, [('holiday_id', '=', False)]]),
            measure_field_name,
            value,
        )

    @api.model
    def _get_recently_used_records(self, groupby_field, domain=None, limit=8):
        domain = Domain.AND([
            domain or [],
            [('holiday_id', '=', False), ('global_leave_id', '=', False)],
        ])
        return super()._get_recently_used_records(groupby_field, domain, limit)
