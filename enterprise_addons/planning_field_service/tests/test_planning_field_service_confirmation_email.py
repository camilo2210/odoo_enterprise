from odoo.addons.mail.tests.common import MailCase

from .common import TestPlanningFieldServiceCommon


class TestPlanningFieldServiceConfirmationEmail(TestPlanningFieldServiceCommon, MailCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner.email = 'customer@example.com'
        cls.default_template = cls.env.ref(
            'planning_field_service.mail_template_data_intervention_details',
        )

    def test_confirmation_email_sent_when_shift_is_published(self):
        self.assertTrue(self.env.company.field_service_confirmation_email)
        self.assertEqual(self.env.company.field_service_confirmation_mail_template_id, self.default_template)
        with self.mock_mail_gateway():
            self.intervention.action_send()
        self.assertTrue(self._find_mail_mail_wemail('customer@example.com', 'sent'))

    def test_confirmation_email_not_sent_when_disabled(self):
        self.env.company.field_service_confirmation_email = False
        with self.mock_mail_gateway():
            self.intervention._send_intervention_scheduled()
        self.assertFalse(self._new_mails)

    def test_confirmation_email_uses_company_template(self):
        custom_template = self.default_template.copy({
            'name': 'Custom Shift Scheduled',
            'subject': 'Custom Confirmation Subject',
        })
        self.env.company.field_service_confirmation_mail_template_id = custom_template
        with self.mock_mail_gateway():
            self.intervention._send_intervention_scheduled()
        self.assertEqual(
            self._find_mail_mail_wemail('customer@example.com', 'sent').subject,
            'Custom Confirmation Subject',
        )

    def test_archiving_template_disables_confirmation_email(self):
        custom_template = self.default_template.copy({'name': 'Template To Archive'})
        self.env.company.field_service_confirmation_mail_template_id = custom_template
        custom_template.action_archive()
        self.assertFalse(self.env.company.field_service_confirmation_email)
        self.assertFalse(self.env.company.field_service_confirmation_mail_template_id)

    def test_deleting_template_disables_confirmation_email(self):
        custom_template = self.default_template.copy({'name': 'Template To Delete'})
        self.env.company.field_service_confirmation_mail_template_id = custom_template
        custom_template.unlink()
        self.assertFalse(self.env.company.field_service_confirmation_email)
        self.assertFalse(self.env.company.field_service_confirmation_mail_template_id)

    def test_archiving_template_disables_confirmation_email_for_every_company(self):
        other_company = self.env['res.company'].create({'name': 'Other Company'})
        custom_template = self.default_template.copy({'name': 'Template To Archive'})
        (self.env.company | other_company).field_service_confirmation_mail_template_id = custom_template
        custom_template.with_context(allowed_company_ids=self.env.company.ids).action_archive()
        self.assertFalse(other_company.field_service_confirmation_email)
        self.assertFalse(other_company.field_service_confirmation_mail_template_id)

    def test_confirmation_email_sent_for_multiple_shifts_at_once(self):
        self.second_intervention.partner_id = self.partner
        with self.mock_mail_gateway():
            (self.intervention | self.second_intervention)._send_intervention_scheduled()
        self.assertEqual(len(self._new_mails), 2)
