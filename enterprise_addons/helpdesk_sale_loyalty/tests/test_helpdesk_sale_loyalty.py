# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.helpdesk.tests import common
from odoo.tests import tagged, Form


@tagged('at_install', '-post_install')  # LEGACY at_install
class TestHelpdeskSaleCoupon(common.HelpdeskCommon):
    """ Test used to check that the functionalities of After sale in Helpdesk (sale_coupon).
    """

    def test_helpdesk_sale_loyalty(self):
        # give the test team ability to create coupons
        self.test_team.use_coupons = True

        ticket = self.env['helpdesk.ticket'].create({
            'name': 'test',
            'partner_id': self.partner.id,
            'team_id': self.test_team.id,
        })
        program = self.env['loyalty.program'].create({
            'name': 'test program',
            'program_type': 'coupons',
            'trigger': 'with_code',
            'applies_on': 'current',
            'reward_ids': [(0, 0, {
                'reward_type': 'discount',
                'discount': 10,
                'discount_mode': 'percent',
                'discount_applicability': 'order',
            })],
        })

        coupon_form = Form(self.env['helpdesk.sale.coupon.generate'].with_context({
            'active_model': 'helpdesk.ticket',
            'default_ticket_id': ticket.id,
        }))
        coupon_form.program = program
        sale_coupon = coupon_form.save()
        composer_action = sale_coupon.action_coupon_generate_send()

        coupon = self.env['loyalty.card'].search([
            ('partner_id', '=', self.partner.id),
            ('program_id', '=', program.id)
        ])

        self.assertEqual(len(coupon), 1, "No coupon created")
        self.assertEqual(len(ticket.coupon_ids), 1,
            "The ticket is not linked to a coupon")
        self.assertEqual(coupon[0], ticket.coupon_ids[0],
            "The correct coupon should be referenced in the ticket")
        self.assertIn("Coupon created", ticket.message_ids[0].preview)

        # simulate the user sending the coupon email from the composer
        attachment = self.env['ir.attachment'].create({
            'name': 'coupon.txt',
            'raw': b'coupon',
        })
        old_ticket_messages = ticket.message_ids
        composer = self.env['mail.compose.message'].with_context(composer_action['context']).create({
            'body': '<p>Here is your coupon code</p>',
            'attachment_ids': [(6, 0, attachment.ids)],
        })
        composer.action_send_mail()

        new_ticket_message = ticket.message_ids - old_ticket_messages
        self.assertEqual(len(new_ticket_message), 1,
            "Sending the coupon email should log exactly one message in the ticket's chatter")
        self.assertIn('Here is your coupon code', new_ticket_message.body,
            "The email body should be logged in the ticket's chatter")
        self.assertIn(attachment, new_ticket_message.attachment_ids,
            "The email attachment should be logged in the ticket's chatter")
