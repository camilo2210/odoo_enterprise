# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo.addons.helpdesk.tests.common import HelpdeskCommon
from odoo.addons.planning_field_service.tests.common import TestPlanningFieldServiceCommon


class TestHelpdeskPlanningFieldService(HelpdeskCommon, TestPlanningFieldServiceCommon):
    def test_ticket_action_plan_intervention(self):
        self.test_team.use_fsm = True

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': self.partner.id,
            'team_id': self.test_team.id,
        })

        intervention_action = ticket.action_plan_intervention()
        self.assertEqual(intervention_action['res_model'], 'planning.slot')
        action_context = intervention_action['context']
        self.assertEqual(action_context['default_helpdesk_ticket_id'], ticket.id)
        self.assertEqual(action_context['default_partner_id'], ticket.partner_id.address_get(['delivery']).get('delivery') or ticket.partner_id.id)
        self.assertEqual(action_context['default_company_id'], ticket.company_id.id)

    def test_ticket_action_view_interventions_default_filter(self):
        self.test_team.use_fsm = True
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': self.partner.id,
            'team_id': self.test_team.id,
        })
        (self.intervention + self.second_intervention).write({'helpdesk_ticket_id': ticket.id})
        action = ticket.action_view_interventions()
        self.assertEqual(action['context']['search_default_helpdesk_ticket_id'], ticket.id)

    def test_intervention_completed(self):
        self.test_team.use_fsm = True
        self.helpdesk_manager.group_ids += self.env.ref('planning.group_planning_user')
        ticket = self.env['helpdesk.ticket'].with_user(self.helpdesk_manager).create({
            'name': 'Ticket',
            'team_id': self.test_team.id,
            'user_id': self.helpdesk_user.id,
            'partner_id': self.partner.id,
        })
        expected_message_count = len(ticket.message_ids) + 1
        intervention_action = ticket.action_plan_intervention()
        context = intervention_action['context']
        intervention = self.env[intervention_action['res_model']].with_context(context).create({
            'start_datetime': datetime.now(),
            'end_datetime': datetime.now() + relativedelta(hours=2),
            'resource_ids': self.current_employee.resource_id.ids,
            'state': '3_in_progress',
        })
        intervention.action_complete()
        self.assertEqual(len(ticket.message_ids), expected_message_count)
        intervention_completed_subtype = self.env.ref('helpdesk_planning_field_service.mt_ticket_intervention_completed', raise_if_not_found=False)
        if intervention_completed_subtype:
            self.assertEqual(ticket.message_ids[0].subtype_id, intervention_completed_subtype, 'A new message should be linked to the ticket saying the intervention has been completed.')
