# Part of Odoo. See LICENSE file for full copyright and licensing details.

import uuid

from odoo import api, fields, models
from odoo.http import request

from odoo.addons.appointment_hr_recruitment.controllers.calendar_view import AppointmentHrRecruitmentCalendarView


class Applicant(models.Model):
    _inherit = "hr.applicant"

    interview_invite_code = fields.Char(readonly=True, copy=False, store=True, precompute=True, compute='_compute_interview_invite_code')

    def _compute_interview_invite_code(self):
        for app in self.filtered(lambda app: not app.interview_invite_code):
            app.interview_invite_code = uuid.uuid4().hex[:16]

    def action_create_meeting(self):
        res = super().action_create_meeting()
        if self.interview_invite_code:
            res['context']['applicant_code'] = self.interview_invite_code
        return res

    def _get_interview_invite_url(self):
        self.ensure_one()
        if not request:
            return ''

        # Skip during installation to avoid registry mismatch between request.env and the new registry
        if self.env.context.get('install_mode'):
            return ''

        return AppointmentHrRecruitmentCalendarView._appointment_type_search_create_anytime(
            user=self.recruiter_id.user_id,
            applicant_code=self.interview_invite_code
        )['invite_url']

    def write(self, vals):
        res = super().write(vals)
        stage_id = vals.get('stage_id', False)
        stage = self.env['hr.recruitment.stage'].browse(stage_id) if stage_id else self.env['hr.recruitment.stage']
        if vals.get('active') is False or (stage and stage.hired_stage):
            meetings_to_archive = self.env['calendar.event'].search([
                ('applicant_id', 'in', self.ids),
                ('start', '>=', fields.Datetime.now()),
                ('active', '=', True)
            ])
            meetings_to_archive.action_archive()
        return res
