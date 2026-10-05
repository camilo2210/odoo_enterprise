from odoo.fields import Command, Date

from odoo.addons.helpdesk.tests.common import HelpdeskCommon
from odoo.addons.hr_holidays.tests.common import TestHrHolidaysCommon
from odoo.addons.mail.tests.common import MailCommon


class TestHelpdeskMailAssignment(HelpdeskCommon, TestHrHolidaysCommon, MailCommon):

    def test_mailgateway_portal_auto_assignment_multicompany(self):
        """Portal email + auto assignment should not crash when a user has employees in multiple companies."""
        company_a = self.env.company
        company_b = self.env['res.company'].create({'name': 'Company B'})

        agent_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Agent X',
            'login': 'agent_x',
            'email': 'agentx@example.com',
            'company_id': company_a.id,
            'company_ids': [Command.set((company_a + company_b).ids)],
        })
        agent_user.write({
            'group_ids': [Command.set(self.env.ref('base.group_user').ids)],
        })

        self.env['hr.employee'].with_company(company_a).create({
            'name': 'Employee A',
            'user_id': agent_user.id,
            'company_id': company_a.id,
            'contract_date_start': Date.today(),
        })
        self.env['hr.employee'].with_company(company_b).create({
            'name': 'Employee B',
            'user_id': agent_user.id,
            'company_id': company_b.id,
            'contract_date_start': Date.today(),
        })

        agent_user_all_companies = agent_user.with_context(
            allowed_company_ids=(company_a + company_b).ids
        )
        self.assertEqual(len(agent_user_all_companies.employee_ids), 2)
        self.assertEqual(len(agent_user_all_companies.resource_ids), 2)

        team = self.test_team
        team.write({
            'company_id': company_a.id,
            'auto_assignment': True,
            'member_ids': [Command.set(agent_user.ids)],
        })

        portal_user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Portal Sender',
            'login': 'portal_sender',
            'email': 'portal.sender@example.com',
            'company_id': company_a.id,
            'company_ids': [Command.set(company_a.ids)],
        })
        portal_user.write({
            'group_ids': [Command.set(self.env.ref('base.group_portal').ids)],
        })

        email_source = f"""From: {portal_user.email_formatted}
To: helpdesk@test.example.com
Subject: Test portal auto assignment multi-company
Content-Type: text/html;

<p>Test Email</p>
"""

        with self.mock_mail_gateway():
            ticket = self.env['mail.thread'].message_process(
                model='helpdesk.ticket',
                message=email_source,
                custom_values={'team_id': team.id},
            )

        self.assertTrue(ticket)
        self.assertEqual(ticket.team_id, team)
        self.assertEqual(ticket.partner_id.email, portal_user.email)
