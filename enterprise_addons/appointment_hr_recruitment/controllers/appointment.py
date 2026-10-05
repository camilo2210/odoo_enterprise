# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.appointment.controllers.appointment import AppointmentController
from odoo import http
from odoo.http import request


class AppointmentHrRecruitmentController(AppointmentController):

    def _get_extra_calendar_event_params(self, **kwargs):
        res = super()._get_extra_calendar_event_params(**kwargs)
        if applicant_code := kwargs.get('applicant_code'):
            applicant_sudo = request.env['hr.applicant'].sudo().search([
                ('interview_invite_code', '=', applicant_code)
            ], limit=1)
            if applicant_sudo:
                res['applicant_id'] = applicant_sudo.id
        return res

    @http.route()
    def appointment_type_page(
        self,
        appointment_type_slug,
        state=False,
        staff_user_id=False,
        resource_selected_id=False,
        **kwargs,
    ):
        if applicant_code := kwargs.get('applicant_code'):
            applicant_sudo = request.env['hr.applicant'].sudo().with_context(active_test=False).search([
                ('interview_invite_code', '=', applicant_code)
            ], limit=1)
            if applicant_sudo and (not applicant_sudo.active or applicant_sudo.stage_id.hired_stage):
                return request.render('appointment_hr_recruitment.appointment_applicant_link_expired')
        return super().appointment_type_page(
            appointment_type_slug,
            state=state,
            staff_user_id=staff_user_id,
            resource_selected_id=resource_selected_id,
            **kwargs,
        )
