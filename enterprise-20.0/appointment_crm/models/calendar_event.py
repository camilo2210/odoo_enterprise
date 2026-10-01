# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import api, fields, models, _


class CalendarEvent(models.Model):
    _inherit = 'calendar.event'

    opportunity_id = fields.Many2one(compute="_compute_opportunity_id", readonly=False, store=True, tracking=True)

    @api.depends('appointment_invite_id')
    def _compute_opportunity_id(self):
        for event in self:
            if event.appointment_invite_id.opportunity_id:
                event.opportunity_id = event.appointment_invite_id.opportunity_id

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        # We want only event with the right appointment type and another attendee than the employee
        events.filtered(
            lambda e: e.appointment_type_id.lead_create and e.partner_ids - e.user_id.partner_id and not e.opportunity_id
        ).sudo()._create_lead_from_appointment()
        for meeting in events.filtered('opportunity_id'):
            if not meeting.meeting_activity_ids:
                meeting.opportunity_id.sudo().activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_meeting',
                    date_deadline=meeting._get_activity_deadline_from_start(meeting.start, meeting.allday),
                    summary=meeting.name,
                    user_id=meeting.user_id.id,
                    calendar_event_id=meeting.id,
                )
            meeting._track_add(
                {meeting.id: {'opportunity_id': meeting.env['crm.lead']}},
                end_values={meeting.id: {'opportunity_id': meeting.opportunity_id}},
                body=Markup("<p>%s</p>") % _(
                    "Meeting linked to Lead/Opportunity %s",
                    meeting.opportunity_id._get_html_link()
                ),
            )
        return events

    def _create_lead_from_appointment(self):
        lead_values = []
        for event in self:
            partner = event.partner_ids - event.user_id.partner_id
            lead_values.append(event._get_lead_values(partner[:1]))

        # Create leads within the event organizer's company
        leads = self.env['crm.lead'].with_context(mail_create_nosubscribe=True) \
            .with_company(self.user_id.company_id).create(lead_values)
        for event, lead in zip(self, leads, strict=True):
            event._link_with_lead(lead)
        return leads

    def _get_lead_values(self, partner):
        return {
            'name': self.name,
            'partner_id': partner.id,
            'type': 'opportunity',
            'user_id': self.user_id.id,
            'description': self.description,
        }

    def _link_with_lead(self, lead):
        self.write({
            'res_model_id': self.env['ir.model']._get(lead._name).id,
            'res_id': lead.id,
            'opportunity_id': lead.id,
        })
