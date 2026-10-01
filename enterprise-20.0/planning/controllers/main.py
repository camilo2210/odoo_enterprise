# Part of Odoo. See LICENSE file for full copyright and licens
import logging
from zoneinfo import ZoneInfo

from odoo import Command, http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

try:
    import vobject
except ImportError:
    _logger.warning("`vobject` Python module not found, vcard file generation disabled. Consider installing this module if you want to generate vcard files")
    vobject = None


class ShiftController(http.Controller):

    @http.route('/planning/assign/<string:token_employee>/<int:shift_id>', type="http", auth="user", website=True)
    def planning_self_assign_with_user(self, token_employee, shift_id, **kwargs):
        slot_sudo = request.env['planning.slot'].sudo().search([('id', '=', shift_id)], limit=1)
        if not slot_sudo:
            return request.not_found()

        employee = request.env.user.employee_id
        if not employee:
            return request.not_found()

        if not slot_sudo.employee_ids:
            slot_sudo.write({'resource_ids': [Command.link(employee.resource_id.id)]})
            slot_sudo.slot_properties  # necessary addition to stop the re-computation of the slot_properties field during the redirect (leads to access rights error)

        return request.redirect('/odoo/action-planning.planning_action_open_shift')

    @http.route('/planning/unassign/<string:token_employee>/<int:shift_id>', type="http", auth="user", website=True)
    def planning_self_unassign_with_user(self, token_employee, shift_id, **kwargs):
        slot_sudo = request.env['planning.slot'].sudo().search([('id', '=', shift_id)], limit=1)
        if not slot_sudo or not slot_sudo.allow_self_unassign:
            return request.not_found()

        if slot_sudo.is_unassign_deadline_passed:
            return request.redirect('/odoo/action-planning.planning_action_open_shift')

        employee = request.env['hr.employee'].sudo().search([('employee_token', '=', token_employee)], limit=1)
        if not employee:
            employee = request.env.user.employee_id
        if not employee or employee not in slot_sudo.employee_ids:
            return request.not_found()

        slot_sudo.write({'resource_ids': [Command.unlink(employee.resource_id.id)]})
        slot_sudo.slot_properties  # necessary addition to stop the re-computation of the slot_properties field during the redirect (leads to access rights error)

        return request.redirect('/odoo/action-planning.planning_action_open_shift')

    @http.route(['/slot/<string:access_token>.ics'], type='http', auth="public", website=True)
    def slot_get_ics_file(self, access_token, **kwargs):
        """
            Route to add the appointment event in a iCal/Outlook calendar
        """
        slot = request.env['planning.slot'].sudo().search([('access_token', '=', access_token)], limit=1)
        if not slot or not vobject:
            return request.not_found()

        tz_set = set(slot.employee_ids.mapped('tz'))
        tz = tz_set.pop() if len(tz_set) == 1 else False
        calendar = slot._get_ics_file(vobject.iCalendar(), tz or request.env.user.tz or 'UTC')
        if not calendar:
            return request.not_found()
        content = calendar.serialize().encode('utf-8')

        shift_name = slot.role_id.name.replace(" ", "_") if slot.role_id else _('New_Shift')
        shift_start_time = slot.start_datetime.astimezone(ZoneInfo(slot._get_tz())).strftime('%m_%d_%H_%M')

        return request.make_response(content, [
            ('Content-Type', 'application/octet-stream'),
            ('Content-Length', len(content)),
            ('Content-Disposition', f'attachment; filename=shift_{shift_name}_{shift_start_time}.ics')
        ])

    @http.route(['/planning/<string:planning_token>/<string:employee_token>.ics'], type='http', auth="public", website=True)
    def planning_get_ics_file(self, planning_token, employee_token, **kwargs):
        """
            Route to add the appointment event in a iCal/Outlook calendar
        """
        employee_sudo = request.env['hr.employee'].sudo().search([('employee_token', '=', employee_token)], limit=1)


        planning_sudo = request.env['planning.planning'].sudo().search([('access_token', '=', planning_token)], limit=1)
        if not (planning_sudo and vobject):
            return request.not_found()

        calendar = planning_sudo._get_ics_file(
            vobject.iCalendar(),
            employee_sudo,
        )
        start_name = planning_sudo.date_start.strftime('%m_%d')
        end_name = planning_sudo.date_end.strftime('%m_%d')
        response = request.make_response(calendar.serialize())
        response.headers.add('Content-Type', 'text/calendar')
        response.headers.add('Content-Disposition', 'attachment', filename=f'planning_{start_name}_to_{end_name}.ics')
        return response
