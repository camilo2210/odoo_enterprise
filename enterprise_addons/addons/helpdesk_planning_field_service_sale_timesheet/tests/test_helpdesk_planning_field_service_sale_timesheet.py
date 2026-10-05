# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests.common import HttpCase
from odoo.addons.helpdesk_planning_field_service.tests.test_helpdesk_planning_field_service import TestHelpdeskPlanningFieldService


class TestHelpdeskPlanningFieldServiceSaleTimesheet(TestHelpdeskPlanningFieldService, HttpCase):

    def test_prevent_traceback_when_opening_interventions(self):
        """Ensure the intervention list is rendered correctly in the portal."""
        self.test_team.use_fsm = True
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Ticket',
            'team_id': self.test_team.id,
            'partner_id': self.helpdesk_portal.partner_id.id,
        })
        context = ticket.action_plan_intervention()['context']
        self.env['planning.slot'].with_context(context).create([
            {
                'start_datetime': '2026-08-19 08:00:00',
                'end_datetime': '2026-08-19 10:00:00',
                'state': '4_completed',
            },
            {
                'start_datetime': '2026-08-19 10:00:00',
                'end_datetime': '2026-08-19 12:00:00',
                'state': '4_completed',
            },
        ])
        self.authenticate(self.helpdesk_portal.login, self.helpdesk_portal.login)
        response = self.url_open(f'/my/tickets/{ticket.id}/interventions')
        self.assertEqual(response.status_code, 200)
