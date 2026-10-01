from freezegun import freeze_time

from odoo.tests import Command, tagged
from odoo.addons.whatsapp.tests.common import WhatsAppCommon
from odoo.addons.account_followup.tests.test_account_followup import TestAccountFollowupReports


@tagged('post_install', '-at_install')
class TestWhatsAppFollowup(WhatsAppCommon, TestAccountFollowupReports):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a.phone = '+32499123456'
        cls.wa_template = cls.env['whatsapp.template'].with_user(cls.user_admin).create({
            'body': 'WhatsApp Followup {{1}}',
            'name': 'WhatsApp Followup test template',
            'status': 'approved',
            'wa_account_id': cls.whatsapp_account.id,
            'variable_ids': [
                Command.create({'name': "{{1}}", 'line_type': "body", 'field_type': 'user_name'}),
            ],
        })

    def create_followup(self, delay):
        followup = super().create_followup(delay)
        followup.send_whatsapp = True
        followup.whatsapp_template_id = self.wa_template
        return followup

    def test_whatsapp_followup_cron(self):
        cron = self.env.ref('account_followup.ir_cron_follow_up')
        self.env.company.automatic_invoice_reminder = True
        followup_10 = self.create_followup(delay=10)

        self._create_invoice_followup('2022-01-01', partner=self.partner_a, post=True)
        with (
            freeze_time('2022-01-11'),
            self.mockWhatsappGateway(),
            self.enter_registry_test_mode(),
        ):
            self.assertPartnerFollowup(self.partner_a, followup_10)
            cron.method_direct_trigger()
            self.assertWAMessageFromRecord(
                self.partner_a,
                fields_values={
                    'body': '<p>WhatsApp Followup OdooBot</p>',
                },
            )
