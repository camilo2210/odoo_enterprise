# Part of Odoo. See LICENSE file for full copyright and licensing details.

from markupsafe import escape

from odoo import fields
from odoo.addons.bus.tests.common import BusResult
from odoo.addons.test_whatsapp.tests.common import WhatsAppFullCase
from odoo.addons.whatsapp.tests.common import MockIncomingWhatsApp
from odoo.tests import tagged, users
from odoo.addons.mail.tests.common import mail_new_test_user


@tagged('wa_message', 'discuss_channel')
class DiscussChannel(WhatsAppFullCase, MockIncomingWhatsApp):

    def test_channel_info_link(self):
        """ Test information posted on channels. Flow

          * a message is sent to the customer;
          * they reply;
          * then another message is posted using a template. This has two
            use cases: either the same user, either another user
          * check record information that should be displayed in channel.
        """
        template = self.whatsapp_template.with_user(self.env.user)
        template_as_admin = self.whatsapp_template.with_user(self.user_wa_admin)
        template_as_emp = self.whatsapp_template.with_user(self.user_employee)
        test_record = self.test_base_record_nopartner.with_env(self.env)

        for reply_template, reply_user, expected_body, error_msg in [
            (
                template_as_admin,
                self.user_wa_admin,
                '<p>Hello World</p>', "Should contain the HTML body of the template sent"
            ), (
                template_as_emp,
                self.user_employee,
                f'<p>A new template was sent on <a target="_blank" '
                f'href="{test_record.get_base_url()}/odoo/{test_record._name}/{test_record.id}">'
                f'{escape(test_record.display_name)}</a>.<br>'
                f'Future replies will be transferred to a new chat.</p>',
                "Should contain channel switch message with related document link"
            ),
        ]:
            with self.subTest(reply_template=template, reply_user=reply_user):
                composer = self._instanciate_wa_composer_from_records(template, test_record)
                with self.mockWhatsappGateway():
                    composer.action_send_whatsapp_template()

                with self.mockWhatsappGateway():
                    self._receive_whatsapp_message(self.whatsapp_account, 'Hello', '32499123456')

                composer = self._instanciate_wa_composer_from_records(reply_template, test_record, reply_user)
                with self.mockWhatsappGateway():
                    composer.action_send_whatsapp_template()

                discuss_channel = self.assertWhatsAppDiscussChannel(
                    "32499123456",
                    wa_msg_count=1, msg_count=3,
                    wa_message_fields_values={
                        'state': 'sent',
                    },
                )

                (second_info, answer, first_info) = discuss_channel.message_ids
                self.assertEqual(second_info.body, expected_body, error_msg)
                self.assertEqual(answer.body, '<p>Hello</p>')
                self.assertIn(
                    first_info.body,
                    f'<p>Related WhatsApp Base Test: <a target="_blank" href="{test_record.get_base_url()}/odoo/'
                    f'{test_record._name}/{test_record.id}">{escape(test_record.display_name)}</a></p>',
                    "Should contain a link and display_name to the new record from which the template was sent"
                )
                self._reset_bus()
                discuss_channel.sudo().unlink()

    @users('user_wa_admin')
    def test_channel_info_link_noname(self):
        """ Test that a channel can be created for a model without a name field
        and rec_name is correctly used for logged info. """
        test_record_noname = self.env['whatsapp.test.nothread.noname'].create({
            'country_id': self.env.ref('base.be').id,
            'customer_id': self.test_partner.id,
        })
        template = self.whatsapp_template.with_user(self.env.user)
        template.write({
            'model_id': self.env['ir.model']._get_id('whatsapp.test.nothread.noname'),
        })

        composer = self._instanciate_wa_composer_from_records(template, test_record_noname)
        with self.mockWhatsappGateway():
            composer.action_send_whatsapp_template()

        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, 'Hello', '32485221100')

        discuss_channel = self.assertWhatsAppDiscussChannel("32485221100", wa_msg_count=1, msg_count=2)
        (answer, first_info) = discuss_channel.message_ids
        self.assertEqual(answer.body, '<p>Hello</p>')
        self.assertIn(
            first_info.body,
            f'<p>Related WhatsApp NoThread / NoResponsible /NoName: <a target="_blank"'
            f' href="{test_record_noname.get_base_url()}/odoo/{test_record_noname._name}/{test_record_noname.id}">'
            f'{escape(test_record_noname.customer_id.name)}</a></p>',
            "Should contain a link and display_name to the new record from which the template was sent")

    @users('user_wa_admin')
    def test_channel_validity_date(self):
        """ Ensure the validity date of a whatsapp channel is only affected by
        messages sent by the whatsapp recipient. """
        template = self.whatsapp_template.with_user(self.env.user)
        test_record = self.test_base_record_nopartner.with_env(self.env)

        composer = self._instanciate_wa_composer_from_records(template, test_record)
        with self.mockWhatsappGateway():
            composer.action_send_whatsapp_template()

        self._receive_whatsapp_message(self.whatsapp_account, 'Hello', '32499123456')

        discuss_channel = self.env["discuss.channel"].search([("whatsapp_number", "=", "32499123456")])
        self.assertTrue(discuss_channel.whatsapp_channel_valid_until)
        first_valid_date = discuss_channel.whatsapp_channel_valid_until

        composer = self._instanciate_wa_composer_from_records(template, test_record)
        with self.mockWhatsappGateway():
            composer.action_send_whatsapp_template()
        second_valid_date = discuss_channel.whatsapp_channel_valid_until

        self.assertEqual(first_valid_date, second_valid_date)

    def test_message_reaction(self):
        """Check a reaction is correctly added on a whatsapp message."""
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, "test", "32499123456")
        discuss_channel = self.assertWhatsAppDiscussChannel("32499123456", wa_msg_count=1, msg_count=1)
        message = discuss_channel.message_ids[0]
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(
                self.whatsapp_account, "", "32499123456",
                additional_message_values={
                    "reaction": {
                        "message_id": message.wa_message_ids[0].msg_uid,
                        "emoji": "😊",
                    },
                    "type": "reaction",
                },
            )

        def message_notifications():
            reactions = message.reaction_ids.filtered(lambda r: r.content == "👍").sorted("id")
            return [
                BusResult(
                    discuss_channel,
                    "mail.record/insert",
                    {
                        "mail.message": self._filter_messages_fields(
                            {
                                "id": message.id,
                                "reactions": [["DELETE", {"message": message.id, "content": "😊"}]],
                            }
                        ),
                    },
                ),
                BusResult(
                    discuss_channel,
                    "mail.record/insert",
                    {
                        "mail.message": self._filter_messages_fields(
                            {
                                "id": message.id,
                                "reactions": [
                                    [
                                        "ADD",
                                        [
                                            {
                                                "content": "👍",
                                                "count": 1,
                                                "guests": [],
                                                "message": message.id,
                                                "partners": message.author_id.ids,
                                                "sequence": reactions[0].id,
                                            },
                                        ],
                                    ],
                                ],
                            },
                        ),
                        "res.partner": self._filter_partners_fields(
                            {
                                "avatar_128_access_token": message.author_id._get_avatar_128_access_token(),
                                "id": message.author_id.id,
                                "name": "+32499123456",
                                "write_date": fields.Datetime.to_string(
                                    message.author_id.write_date
                                ),
                            }
                        ),
                    },
                ),
            ]

        with self.assertBus(message_notifications):
            with self.mockWhatsappGateway():
                self._receive_whatsapp_message(
                    self.whatsapp_account, "", "32499123456",
                    additional_message_values={
                        "reaction": {
                            "message_id": message.wa_message_ids[0].msg_uid,
                            "emoji": "👍",
                        },
                        "type": "reaction",
                    },
                )
        self.assertEqual(len(message.reaction_ids), 1, "One reaction should be present.")
        self.assertEqual(message.reaction_ids.content, "👍", "The reaction emoji should be 👍.")
        partner_wa_admin = self.user_wa_admin.partner_id

        def res_for_partner(partner):
            return {
                "avatar_128_access_token": partner._get_avatar_128_access_token(),
                "id": partner.id,
                "name": partner.name,
                "write_date": fields.Datetime.to_string(partner.write_date),
            }

        def add_rocket_notifications():
            reactions = message.reaction_ids.filtered(lambda r: r.content == "🚀").sorted("id")
            return [
                BusResult(
                    discuss_channel,
                    "mail.record/insert",
                    {
                        "mail.message": self._filter_messages_fields(
                            {
                                "id": message.id,
                                "reactions": [
                                    [
                                        "ADD",
                                        [
                                            {
                                                "content": "🚀",
                                                "count": 1,
                                                "guests": [],
                                                "message": message.id,
                                                "partners": partner_wa_admin.ids,
                                                "sequence": reactions[0].id,
                                            }
                                        ],
                                    ]
                                ],
                            }
                        ),
                        "res.partner": self._filter_partners_fields(
                            res_for_partner(partner_wa_admin),
                        ),
                    },
                ),
            ]

        def add_fire_notifications():
            reactions = message.reaction_ids.filtered(lambda r: r.content == "🔥").sorted("id")
            return [
                BusResult(
                    discuss_channel,
                    "mail.record/insert",
                    {
                        "mail.message": self._filter_messages_fields(
                            {
                                "id": message.id,
                                "reactions": [["DELETE", {"message": message.id, "content": "🚀"}]],
                            }
                        ),
                    },
                ),
                BusResult(
                    discuss_channel,
                    "mail.record/insert",
                    {
                        "mail.message": self._filter_messages_fields(
                            {
                                "id": message.id,
                                "reactions": [
                                    [
                                        "ADD",
                                        [
                                            {
                                                "content": "🔥",
                                                "count": 1,
                                                "guests": [],
                                                "message": message.id,
                                                "partners": partner_wa_admin.ids,
                                                "sequence": reactions[0].id,
                                            }
                                        ],
                                    ]
                                ],
                            }
                        ),
                        "res.partner": self._filter_partners_fields(
                            res_for_partner(partner_wa_admin),
                        ),
                    },
                ),
            ]

        self.authenticate(self.user_wa_admin.login, self.user_wa_admin.login)
        with self.mockWhatsappGateway():
            # Add first reaction 🚀 (user sent)
            with self.assertBus(add_rocket_notifications):
                self.make_jsonrpc_request(
                    "/mail/message/reaction",
                    {"action": "add", "content": "🚀", "message_id": message.id},
                )
            # Assert total 2 reactions now (🚀 from Odoo user, 👍 from WA user)
            reactions = message.reaction_ids
            self.assertEqual(len(reactions), 2)
            self.assertSetEqual(set(reactions.mapped("content")), {"🚀", "👍"})
            # Replace 🚀 with 🔥
            with self.assertBus(add_fire_notifications):
                self.make_jsonrpc_request(
                    "/mail/message/reaction",
                    {"action": "add", "content": "🔥", "message_id": message.id},
                )
            # Assert reaction still count to 2, and Odoo user reaction is 🔥
            reactions = message.reaction_ids
            self.assertEqual(len(reactions), 2)
            self.assertSetEqual(set(reactions.mapped("content")), {"🔥", "👍"})
            # Try re-adding 🔥 (should not resend API call)
            with self.assertBus([]):
                self.make_jsonrpc_request(
                    "/mail/message/reaction",
                    {"action": "add", "content": "🔥", "message_id": message.id},
                )
            self.assertEqual(len(self._wa_msg_sent_vals), 2, "Two API calls should've been made for two different emojis (🚀 → 🔥).")
            self.assertEqual(self._wa_msg_sent_vals[-1]["emoji"], "🔥", "Last API call should've sent 🔥 as emoji.")


@tagged('wa_message')
class DiscussChannelMultiUsers(WhatsAppFullCase, MockIncomingWhatsApp):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user_employee_2 = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            country_id=cls.env.ref('base.us').id,
            groups='base.group_user,mail.group_mail_template_editor',
            login='employee_2',
            name='Arthur Employee',
            notification_type='email',
            signature='--\nArthur'
        )

        cls.whatsapp_account.write({'notify_user_ids': [(4, cls.user_employee.id), (4, cls.user_employee_2.id)]})

        country_us_id = cls.env.ref('base.be').id
        cls.test_partner_us = cls.env['res.partner'].create({
            'country_id': country_us_id,
            'email': 'whatsapp.customer@test.example.com',
            'name': 'WhatsApp Customer',
            'phone': '+1 804-555-0268',
        })

        cls.test_base_us_records = cls.env['whatsapp.test.base'].create([
            {
                'country_id': country_us_id,
                'name': "Test <b>Without Partner</b>r",
                'phone': '+1 804-555-0268',
            }, {
                'country_id': country_us_id,
                'customer_id': cls.test_partner_us.id,
                'name': "Test <b>With partner</b>",
            }
        ])
        cls.test_base_us_record_nopartner, cls.test_base_us_record_partner = cls.test_base_us_records

    def test_receiving_unformatted_number(self):
        """
        Verify that messages from the same phone number, whether formatted or
        unformatted, are routed to the same discuss channel. Templates are
        created with the formatted number, but WhatsApp may deliver incoming
        messages using the unformatted variant.
        :param self: Description
        """
        self.send_template(self.whatsapp_template,
                                     self.test_base_us_record_partner,
                                     with_user=self.user_employee
                                     )

        not_formatted_sender_phone_number = '+1 804-555-0268'
        formatted_sender_phone_number = '18045550268'

        # Send and checks the unformatted number correctly stores the template message with formatted number but doesnt associate the template whatsapp message with the dicuss channel.
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, 'Hello', not_formatted_sender_phone_number)
        # stores both the template message and the received whatsapp message in the same discuss channel therefore wa_msg_count=1, msg_count=2
        discuss_channel_1 = self.assertWhatsAppDiscussChannel('18045550268', wa_msg_count=1, msg_count=2)
        self.assertEqual(len(discuss_channel_1), 1, f'Should find exactly one channel for number {formatted_sender_phone_number}')

        # Checking The responsible users
        channel_members = discuss_channel_1.channel_member_ids.mapped('partner_id')
        self.assertEqual(len(channel_members), 2)
        self.assertNotIn(self.user_wa_admin.partner_id, channel_members)
        self.assertIn(self.user_employee.partner_id, channel_members)
        self.assertNotIn(self.user_employee_2.partner_id, channel_members)
        self.assertIn(self.test_partner_us, channel_members)

        # Send and check the formatted number finds the same discuss channel as the unformatted number.
        # Stores both the template message and both received whatsapp message in the same discuss channel therefore wa_msg_count=2, msg_count=3
        with self.mockWhatsappGateway():
            self._receive_whatsapp_message(self.whatsapp_account, 'Hello again', formatted_sender_phone_number)
        discuss_channel_2 = self.assertWhatsAppDiscussChannel('18045550268', wa_msg_count=2, msg_count=3)
        self.assertEqual(len(discuss_channel_2), 1, f'Should find exactly one channel for number {formatted_sender_phone_number}')
        self.assertEqual(discuss_channel_1.id, discuss_channel_2.id, 'Both discuss channels should be the same')
