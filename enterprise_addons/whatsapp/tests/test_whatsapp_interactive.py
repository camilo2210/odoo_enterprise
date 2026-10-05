from odoo import Command
from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged, users


class WhatsAppInteractiveCase(WhatsAppCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._prepare_interactive_templates()


@tagged('wa_interactive')
class WhatsAppInteractiveValidation(WhatsAppInteractiveCase):
    """Tests for interactive template validations and computed field logic."""

    @users('user_wa_admin')
    def test_interactive_buttons_cta_url_validation(self):
        invalid_button_write_vals = [
            ([], 'An interactive template must have at least one button.'),
            ([
                {'name': 'CTA URL Button 1', 'button_type': 'url', 'website_url': 'https://odoo.com'},
                {'name': 'CTA URL Button 2', 'button_type': 'url', 'website_url': 'https://odoo.com'},
            ], "A 'CTA URL' message type should only have one button."),
        ]

        for button_vals, exp_error in invalid_button_write_vals:
            with self.subTest(button_vals=button_vals), self.assertRaisesRegex(ValidationError, exp_error):
                self.test_interactive_cta_url.write({
                    'button_ids': [Command.clear()] + [Command.create(vals) for vals in button_vals],
                })

    @users('user_wa_admin')
    def test_interactive_buttons_list_validation(self):
        invalid_button_write_vals = [
            ([], 'An interactive template must have at least one button.'),
            ([
                {'name': 'Section', 'button_type': 'section'} for _ in range(11)
            ], 'Maximum 10 sections are allowed.'),
            ([
                {'name': 'Question', 'description': 'Description', 'button_type': 'question'} for _ in range(11)
            ], 'Maximum 10 questions are allowed'),
            ([
                {'name': 'Question 1', 'button_type': 'question', 'description': 'Description 1'},
                {'name': 'Section 1', 'button_type': 'section'},
            ], 'If there are sections, the first item must be a section.'),
            ([
                {'name': 'Section 1', 'button_type': 'section'},
            ], 'The last list item must be a question.'),
            ([
                {'name': 'Section 1', 'button_type': 'section'},
                {'name': 'Section 2', 'button_type': 'section'},
                {'name': 'Question 2', 'description': 'Description 2', 'button_type': 'question'},
            ], 'Each section must be followed by at least one question.'),
        ]

        for button_vals, exp_error in invalid_button_write_vals:
            with self.subTest(button_vals=button_vals), self.assertRaisesRegex(ValidationError, exp_error):
                self.test_interactive_list.write({
                    'button_ids': [Command.clear()] + [Command.create(vals) for vals in button_vals],
                })

    @users('user_wa_admin')
    def test_interactive_buttons_reply_validation(self):
        invalid_button_write_vals = [
            ([], 'An interactive template must have at least one button.'),
            ([
                {'name': 'Test Reply Button 1'},
                {'name': 'Test Reply Button 2'},
                {'name': 'Test Reply Button 3'},
                {'name': 'Test Reply Button 4'},
            ], "An 'Interactive Reply Buttons' message type must have between 1 and 3 buttons."),
            ([
                {'name': 'Test Reply Button'},
                {'name': 'Test Reply Button'},
            ], 'Each button must have a unique name.'),
        ]

        for button_vals, exp_error in invalid_button_write_vals:
            with self.subTest(button_vals=button_vals), self.assertRaisesRegex(ValidationError, exp_error):
                self.test_interactive_reply.write({
                    'button_ids': [Command.clear()] + [Command.create(vals) for vals in button_vals],
                })

    @users('user_wa_admin')
    def test_interactive_buttons_type_validation(self):
        invalid_button_types = [
            (self.test_interactive_cta_url, [{'name': 'Reply', 'button_type': 'quick_reply'}], 'url'),
            # button_type defaults to quick_reply outside of the form-view context.
            (self.test_interactive_list, [{'name': 'Default Reply'}], 'question or section'),
            (self.test_interactive_reply, [{'name': 'URL', 'button_type': 'url'}], 'quick_reply'),
        ]

        for interactive, button_vals, exp_allowed_types in invalid_button_types:
            exp_error = (
                f"Button types for a '{interactive.interactive_type}' interactive template "
                f"must be one of: {exp_allowed_types}."
            )
            with self.subTest(interactive_type=interactive.interactive_type, button_vals=button_vals), \
                    self.assertRaisesRegex(ValidationError, exp_error):
                interactive.write({
                    'button_ids': [Command.clear()] + [Command.create(vals) for vals in button_vals],
                })

    @users('user_wa_admin')
    def test_interactive_header_text_validation(self):
        exp_error = 'Markdown is not allowed inside Header Text.'
        # markup is not allowed in header text
        for header_text in [
            '*Header Text*',
            '_Header Text_',
            '~Header Text~',
            '```Header Text```',
        ]:
            with self.subTest(header_text=header_text), self.assertRaisesRegex(ValidationError, exp_error):
                self.test_interactive_list.write({
                    'header_type': 'text',
                    'header_text': header_text,
                })


@tagged('wa_interactive')
class WhatsAppInteractiveForm(WhatsAppInteractiveCase):
    """Form-based tests covering compute and inverse logic"""

    @users('user_wa_admin')
    def test_interactive_button_reset_on_type_change(self):
        """Test button_ids reset on interactive_type change"""
        interactive_form = Form(self.test_interactive_list)
        self.assertTrue(interactive_form.button_ids)
        interactive_form.interactive_type = 'button'
        self.assertFalse(interactive_form.button_ids)

    @users('user_wa_admin')
    def test_interactive_button_url_autoprefix(self):
        """Test auto-prefixing 'https://' to website_url if missing"""
        interactive_form = Form(self.test_interactive_cta_url)
        with interactive_form.button_ids.edit(0) as button:
            button.name = 'Test Https Prefix'
            button.website_url = 'runbot.odoo.com'
            self.assertEqual(button.website_url, 'https://runbot.odoo.com')

    @users('user_wa_admin')
    def test_interactive_header_type_reset_on_type_change(self):
        """Test header_type reset on interactive_type change"""
        interactive_form = Form(self.test_interactive_reply)
        interactive_form.header_type = 'image'
        interactive_form.interactive_type = 'list'
        self.assertEqual(interactive_form.header_type, 'none')


@tagged('wa_interactive')
class WhatsAppInteractivePreview(WhatsAppInteractiveCase):
    """Tests preview rendering logic for interactive messages, including markup conversion and layout."""

    @users('user_wa_admin')
    def test_interactive_preview(self):
        """Test preview feature of interactive itself"""
        interactive_list = self.test_interactive_list
        interactive_list.write(
            {
                'body': 'Feel *free* to *contact* us; Odoo is ~great~ ~super~ super great !',
                'footer_text': 'Thank *you*',
                'header_text': 'Interactive Header',
                'header_type': 'text',
            }
        )

        # Create a preview and check expected values
        preview = self.env['whatsapp.preview'].create(
            {'wa_interactive_id': interactive_list.id}
        )
        expected_preview_texts = [
            'Interactive Header',  # Header text
            'Feel <b>free</b> to <b>contact</b> us; Odoo is <s>great</s> <s>super</s> super great !',  # Body text
            'Thank <b>you</b>',  # Footer text
            interactive_list.list_button_label,  # Button label from the interactive list
        ]
        for expected_text in expected_preview_texts:
            with self.subTest(expected_text=expected_text):
                self.assertIn(expected_text, preview.preview_whatsapp)
