# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests.common import tagged, HttpCase
from .common import HelpdeskCommon


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHelpdeskPortal(HttpCase, HelpdeskCommon):
    def test_customer_closure(self):
        self.test_team.allow_portal_ticket_closing = True
        self.test_team.privacy_visibility = 'portal'

        portal_user = mail_new_test_user(
            self.env,
            name='helpdesk_portal',
            login='helpdesk_portal',
            email='helpdesk@portal.com',
            groups='base.group_portal',
        )

        ticket = self.env['helpdesk.ticket'].create({
                'name': 'Test Ticket',
                'team_id': self.test_team.id,
                'stage_id': self.stage_new.id,
                'user_id': self.helpdesk_user.id,
        })

        self.assertFalse(ticket.closed_by_partner, 'The ticket should not be closed by the customer.')

        self.authenticate(portal_user.login, portal_user.login)
        response = self.url_open(f"/my/ticket/close/{ticket.id}/{ticket.access_token}")

        self.assertEqual(response.status_code, 200, 'The request should be successful.')
        self.assertTrue(ticket.closed_by_partner, 'The ticket should be closed by the customer.')
        self.assertEqual(ticket.stage_id, self.stage_done, 'The ticket should be moved to the Done stage.')

    def test_ignore_mail_scanner_closure(self):
        """Only GET requests should lead to a ticket being closed."""
        self.test_team.allow_portal_ticket_closing = True
        self.test_team.privacy_visibility = 'portal'

        ticket = self.env['helpdesk.ticket'].create({
                'name': 'Test Ticket',
                'team_id': self.test_team.id,
                'stage_id': self.stage_new.id,
                'user_id': self.helpdesk_user.id,
        })

        url = f"/my/ticket/close/{ticket.id}/{ticket.access_token}"
        self.url_open(url, method='HEAD')
        self.assertFalse(ticket.closed_by_partner)
        self.url_open(url)
        self.assertTrue(ticket.closed_by_partner)

    def test_portal_user_see_all_company_ticket(self):
        """
        Steps:
            - Create HelpdeskTicket model shortcut.
            - Create a child portal user.
            - Link user_c as a child of Helpdesk Portal.
            - Create an extra child partner.
            - Create three helpdesk tickets: two for parent, one for child.
            - Test that parent sees their own + children's tickets.
        """
        HelpdeskTicket = self.env['helpdesk.ticket']
        child_helpdesk_portal = mail_new_test_user(
            self.env,
            name='child_partner',
            login='child_partner',
            email='child@partner.com',
            groups='base.group_portal',
        )

        child_helpdesk_portal.partner_id.parent_id = self.helpdesk_portal.partner_id.id

        child_partner2 = self.env['res.partner'].create({
            'name': 'child_partner2',
            'parent_id': self.helpdesk_portal.partner_id.id,
        })

        HelpdeskTicket.create([
            {
                'name': 'test ticket',
                'team_id': self.test_team.id,
                'partner_id': self.helpdesk_portal.partner_id.id,
            },
            {
                'name': 'test ticket',
                'team_id': self.test_team.id,
                'partner_id': self.helpdesk_portal.partner_id.id,
            },
            {
                'name': 'test ticket',
                'team_id': self.test_team.id,
                'partner_id': child_partner2.id,
            },
        ])

        parent_ticket_count = HelpdeskTicket.with_user(self.helpdesk_portal).search_count([])
        self.assertEqual(
            parent_ticket_count,
            3,
            'Parent partner should be able to see tickets created by its children.'
        )

        child_ticket_count = HelpdeskTicket.with_user(child_helpdesk_portal).search_count([])
        self.assertEqual(
            child_ticket_count,  # +2 because child can see parent's ticket
            3,
            'Child partner should be able to see tickets created by its parent and siblings.'
        )
