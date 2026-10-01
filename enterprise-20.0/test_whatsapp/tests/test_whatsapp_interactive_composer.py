from datetime import datetime, timedelta
from freezegun import freeze_time

from odoo.addons.test_whatsapp.tests.common import WhatsAppFullCase
from odoo.exceptions import UserError
from odoo.tests import tagged, users


@tagged('wa_interactive')
class WhatsAppInteractiveComposerRendering(WhatsAppFullCase):
    """Test rendering based on various interactive types, notably using
    dynamic headers"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._prepare_interactive_templates()
        cls.test_wa_channel = cls.env['discuss.channel'].create({
            'channel_partner_ids': [(4, cls.user_employee.partner_id.id)],
            'channel_type': 'whatsapp',
            'name': 'Dummy WA Channel with interactive templates',
            'wa_account_id': cls.whatsapp_account.id,
            'whatsapp_number': '919876543210',
            'whatsapp_partner_id': cls.whatsapp_customer.id,
        })
        # an interactive message only goes out in an open conversation, which
        # starts at the last message received from the customer
        cls.test_wa_channel.last_wa_mail_message_id = cls.env['mail.message'].create({
            'author_id': cls.whatsapp_customer.id,
            'message_type': 'whatsapp_message',
            'model': 'discuss.channel',
            'res_id': cls.test_wa_channel.id,
        })

    @users('employee')
    def test_interactive_composer_basic(self):
        """Test sending interactive messages
        via the interactive composer."""
        interactive_cta_url = self.test_interactive_cta_url.with_user(self.env.user)
        interactive_list = self.test_interactive_list.with_user(self.env.user)
        interactive_reply = self.test_interactive_reply.with_user(self.env.user)
        list_buttons = interactive_list.button_ids

        for interactive, exp_field_values, exp_action_values in [
            (
                interactive_cta_url,
                {'body': '<p>Test Interactive CTA URL body</p>'},
                {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': 'Test CTA URL Button',
                        'url': 'https://www.odoo.com',
                    },
                },
            ),
            (
                interactive_list,
                {'body': '<p>Test Interactive List body</p>'},
                {
                    'button': 'Test List Button',
                    'sections': [
                        {
                            'title': list_buttons[0].name,
                            'rows': [
                                {'id': str(list_buttons[1].id), 'title': 'Question 1', 'description': 'Description 1'},
                                {'id': str(list_buttons[2].id), 'title': 'Question 2', 'description': 'Description 2'},
                            ],
                        },
                        {
                            'title': list_buttons[3].name,
                            'rows': [
                                {'id': str(list_buttons[4].id), 'title': 'Question 3', 'description': 'Description 3'},
                                {'id': str(list_buttons[5].id), 'title': 'Question 4', 'description': 'Description 4'},
                            ],
                        },
                    ],
                },
            ),
            (
                interactive_reply,
                {'body': '<p>Test Interactive Reply body</p>'},
                {
                    'buttons': [
                        {'type': 'reply', 'reply': {'id': str(button.id), 'title': button.name}}
                        for button in interactive_reply.button_ids
                    ],
                },
            ),
        ]:
            with self.subTest(interactive=interactive.name):
                composer = self._instantiate_wa_interactive_composer_from_channel(
                    interactive, self.test_wa_channel,
                )
                with self.mockWhatsappGateway():
                    composer.action_send_whatsapp_interactive()

                self.assertWAMessage(
                    fields_values=exp_field_values,
                )
                self.assertEqual(self._wa_msg_sent_vals, [{
                    'type': interactive.interactive_type,
                    'body': {'text': interactive.body},
                    'action': exp_action_values,
                }])

    @users('employee')
    def test_interactive_composer_closed_conversation(self):
        """Test that an interactive message cannot be sent once the
        24 hours window is over."""
        composer = self._instantiate_wa_interactive_composer_from_channel(
            self.test_interactive_reply, self.test_wa_channel,
        )
        with freeze_time(datetime.now() + timedelta(hours=25)), \
                self.assertRaisesRegex(UserError, 'Conversation closed'):
            composer.action_send_whatsapp_interactive()

    @users('employee')
    def test_interactive_composer_header_various(self):
        """Test sending interactive messages via the
        interactive composer with various headers."""

        for header_type, interactive_write_vals, exp_att_values, exp_field_values in (
            (
                'text',
                {'header_text': 'Test Header Text'},
                {},
                {'body': '<p><b>Test Header Text</b></p><p>Test Interactive Reply body</p>'},
            ), (
                'image',
                {'header_attachment_id': self.image_attachment.id},
                {'name': self.image_attachment.name, 'raw': self.image_attachment.raw.content},
                {'body': '<p>Test Interactive Reply body</p>'},
            ), (
                'video',
                {'header_attachment_id': self.video_attachment.id},
                {'name': self.video_attachment.name, 'raw': self.video_attachment.raw.content},
                {'body': '<p>Test Interactive Reply body</p>'},
            ), (
                'document',
                {'header_attachment_id': self.document_attachment.id},
                {'name': self.document_attachment.name, 'raw': self.document_attachment.raw.content},
                {'body': '<p>Test Interactive Reply body</p>'},
            ),
        ):
            with self.subTest(header_type=header_type):
                # Update the interactive record
                self.test_interactive_reply.write({
                    'header_type': header_type,
                    **interactive_write_vals,
                })
                interactive_reply = self.test_interactive_reply.with_user(self.env.user)

                # Send the interactive message
                composer = self._instantiate_wa_interactive_composer_from_channel(
                    interactive_reply, self.test_wa_channel,
                )
                with self.mockWhatsappGateway():
                    composer.action_send_whatsapp_interactive()

                # Verify the sent interactive message
                self.assertWAMessage(
                    attachment_values=exp_att_values,
                    fields_values=exp_field_values,
                )
