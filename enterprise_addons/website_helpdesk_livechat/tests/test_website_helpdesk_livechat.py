# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup

from odoo import Command
from odoo.addons.bus.tests.common import BusCase, BusResult
from odoo.tests.common import HttpCase
from odoo.addons.helpdesk.tests.common import HelpdeskCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestWebsiteHelpdeskLivechat(HttpCase, HelpdeskCommon, BusCase):
    def setUp(self):
        super().setUp()
        self.maxDiff = None
        self.livechat_channel = self.env['im_livechat.channel'].create({
            'name': 'The channel',
            'user_ids': [Command.set([self.helpdesk_manager.id])]
        })

        user = self.helpdesk_manager
        user.group_ids |= self.env.ref('im_livechat.im_livechat_group_user')

        def _compute_available_operator_ids(channel_self):
            for record in channel_self:
                record.available_operator_ids = user

        self.patch(type(self.env['im_livechat.channel']), '_compute_available_operator_ids', _compute_available_operator_ids)

        self.test_team.use_website_helpdesk_livechat = True

    def test_helpdesk_commands(self):
        teams = self.env['helpdesk.team'].search([('use_website_helpdesk_livechat', '=', True), ('id', '!=', self.test_team.id)])
        teams.use_website_helpdesk_livechat = False
        data = self.make_jsonrpc_request(
            "/im_livechat/get_session", {"channel_id": self.livechat_channel.id}
        )
        discuss_channel = self.env['discuss.channel'].browse(data["channel_id"]).with_user(self.helpdesk_manager)

        self.assertFalse(self.env['helpdesk.ticket'].search([('team_id', '=', self.test_team.id)]), 'The team should start with no tickets')

        # Post a message that will be part of the chat history in the ticket description
        test_message = 'Test message'
        discuss_channel.message_post(body=test_message, message_type="comment")
        # Create both image and text-type attachments.
        attachments = self.env['ir.attachment'].create([{
            'name': "Image attachment",
            'res_model': 'discuss.channel',
            'res_id': discuss_channel.id,
            'raw': b'My attachment',
            'mimetype': 'image/png',
        }, {
            'name': "Text attachment",
            'res_model': 'discuss.channel',
            'res_id': discuss_channel.id,
            'raw': b'My attachment',
        }])

        # Post message with the created attachments
        discuss_channel.message_post(attachment_ids=attachments.ids, message_type="comment")

        # Create ticket with /ticket command and empty title to get the help message
        expected_transient_message = (
            "<span class='o_mail_notification'>"
            "Create a new helpdesk ticket with: <pre>/ticket <i>ticket title</i></pre>"
            "</span>"
        )

        def notifications(body):
            self.env.cr.execute("SELECT currval('mail_message_id_seq')")
            message_id = self.env.cr.fetchone()[0]
            return [
                BusResult(
                    self.helpdesk_manager,
                    "mail.record/insert",
                    {
                        "mail.message": [
                            {
                                "author_id": self.env.ref("base.partner_root").id,
                                "body": ["markup", body],
                                "id": message_id,
                                "is_transient": True,
                                "subtype_id": self.env.ref("mail.mt_note").id,
                                "thread": {"id": discuss_channel.id, "model": "discuss.channel"},
                            },
                        ],
                        "mail.thread": [
                            {
                                "id": discuss_channel.id,
                                "messages": [["ADD", [message_id]]],
                                "model": "discuss.channel",
                                "transientMessages": [["ADD", [message_id]]],
                            },
                        ],
                    },
                ),
            ]

        with self.assertBus(lambda: notifications(expected_transient_message)):
            discuss_channel.execute_command_helpdesk(body="/ticket")

        # Create the ticket with the /ticket command
        ticket_name = 'Test website helpdesk livechat'
        discuss_channel.execute_command_helpdesk(body=f"/ticket {ticket_name}")
        self.assertTrue(discuss_channel.sudo().ticket_ids)

        message = discuss_channel.message_ids[0]
        ticket = self.env['helpdesk.ticket'].search([('team_id', '=', self.test_team.id)])
        self.assertIn('<div data-embedded="file"', ticket.description,
            'The name "Text attachment" should be added to the ticket description.')
        self.assertIn(f'<img src="{attachments[0].image_src}?access_token={attachments[0].access_token}" alt="Image attachment"', ticket.description,
            "The image attachment should be added to the ticket description.")
        self.assertEqual(ticket.message_attachment_count, 1,
            'Only one text-type attachment should be attached to the ticket.')
        expected_message = Markup(
            '<div class="o_mail_notification" data-oe-type="create-ticket">created a new ticket: '
            '<a href="#" data-oe-model="helpdesk.ticket" data-oe-id="%(ticket_id)s">'
            '%(ticket_name)s (#%(ticket_ref)s)</a></div>'
        ) % {
            "ticket_id": ticket.id,
            "ticket_name": ticket_name,
            "ticket_ref": ticket.ticket_ref,
        }
        self.assertTrue(ticket, f"Ticket {ticket_name} should have been created.")
        self.assertEqual(message.body, expected_message, "A message should be posted with a link to the created ticket.")
        self.assertIn(ticket_name, ticket.name, f"The created ticket should be named '{ticket_name}'.")
        self.assertIn(test_message, f"{self.helpdesk_manager.name}: {str(ticket.description)}", 'The chat history should be in the ticket description.')

        # Search the tickets with the /search_tickets command
        expected_message = f"<span class='o_mail_notification'>Tickets search results for <b>Test website helpdesk livechat</b>: <br/><a href=# data-oe-model='helpdesk.ticket' data-oe-id='{ticket.id}'>{ticket_name} (#{ticket.ticket_ref})</a></span>"
        with self.assertBus(lambda: notifications(expected_message)):
            discuss_channel.execute_command_helpdesk_search(body=f"/search_tickets {ticket_name}")

        # Create 5 additional tickets with similar name as the previous ticket
        for i in range(5):
            discuss_channel.execute_command_helpdesk(body=f"/ticket {ticket_name}{i}")

        extra_tickets = self.env["helpdesk.ticket"].search(
            [("name", "in", [f"{ticket_name}{i}" for i in range(5)])], order="id desc"
        )
        ticket_links = "<br/>".join(
            f"<a href=# data-oe-model='helpdesk.ticket' data-oe-id='{extra_ticket.id}'>"
            f"{extra_ticket.name} (#{extra_ticket.ticket_ref})</a>"
            for extra_ticket in extra_tickets
        )
        load_more_link = f'<div class="o_load_more"><b><a href="#" data-oe-type="load" data-oe-lst="{ticket_name}" data-oe-load-counter="1">Load More</a></b></div>'
        expected_message = (
            "<span class='o_mail_notification'>Tickets search results for "
            f"<b>{ticket_name}</b>: <br/>{ticket_links}<br/>{load_more_link}</span>"
        )
        with self.assertBus(lambda: notifications(expected_message)):
            discuss_channel.execute_command_helpdesk_search(body=f"/search_tickets {ticket_name}")

    def test_chatbot_script_steps_with_create_ticket(self):
        with self.assertRaises(ValidationError):
            self.env['chatbot.script'].create({
                'title': 'Chatbot 1',
                'script_step_ids': [Command.create({'step_type': 'create_ticket'})]
            })

        self.env['chatbot.script'].create({
            'title': 'Chatbot 2',
            'script_step_ids': [
                Command.create({'step_type': 'question_email'}),
                Command.create({'step_type': 'create_ticket'}),
            ]
        })

    def test_store_livechat_extra_fields(self):
        parent_partner, other_partner = self.env["res.partner"].create(
            [
                {"name": "Parent Partner"},
                {"name": "Other Partner"},
            ]
        )
        child_partner = self.env["res.partner"].create(
            {
                "name": "Child Partner",
                "parent_id": parent_partner.id,
            }
        )
        helpdesk_team = self.env["helpdesk.team"].create(
            {
                "name": "Test Team",
                "message_follower_ids": [
                    Command.create(
                        {
                            "res_model": "helpdesk.team",
                            "partner_id": self.helpdesk_manager.partner_id.id,
                        }
                    )
                ],
            }
        )
        discuss_channel = self.env["discuss.channel"].create(
            {
                "channel_member_ids": [
                    Command.create({"partner_id": parent_partner.id, "livechat_member_type": "visitor"})
                ],
                "channel_type": "livechat",
                "livechat_channel_id": self.livechat_channel.id,
                "name": "Test Channel",
            }
        )
        self.env["helpdesk.ticket"].create(
            [
                {
                    "name": "Ticket 1",
                    "partner_id": parent_partner.id,
                    "team_id": helpdesk_team.id,
                },
                {
                    "name": "Ticket 2",
                    "partner_id": child_partner.id,
                    "team_id": helpdesk_team.id,
                },
                {
                    "name": "Ticket Not Related",
                    "partner_id": other_partner.id,
                    "team_id": helpdesk_team.id,
                },
            ]
        )
        self.start_tour(
            f"/odoo/discuss?active_id=discuss.channel_{discuss_channel.id}",
            "helpdesk_livechat_info_panel_tour",
            login="hm",
        )
