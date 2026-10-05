from freezegun import freeze_time
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestHUIntrastat(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('hu')
    def setUpClass(cls):
        super().setUpClass()
        cls.report_goods = cls.env.ref('account_intrastat.intrastat_report')
        cls.report_handler = cls.env['account.intrastat.goods.report.handler']
        cls.company_data['company'].vat = '27725414-2-13'
        cls.partner_a.write({
            'name': 'PARTNER BE',
            'country_id': cls.env.ref('base.be').id,
            'vat': 'BE0396779488',
        })

    @classmethod
    def _patch_generate_locking_attachments(cls):
        return patch.object(cls.registry['account.return'], '_generate_locking_attachments', lambda self, options: None)

    @freeze_time('2025-02-01')
    def test_hu_intrastat_export(self):
        # Datas
        company = self.company_data['company']
        user = self.env['res.users'].create({
            'login': 'demo_user',
            'name': 'User with restricted rights',
            'email': 'user@test.test',
            'group_ids': [Command.link(self.env.ref('account.group_account_user').id)],
            'company_ids': [Command.link(company.id)],
            'company_id': company.id,
        })
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'intrastat_code_id': self.env.ref('account_intrastat.commodity_code_2018_1063910').id,
            'intrastat_supplementary_unit_amount': 1,
        })
        self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_a.id,
            'invoice_date': '2025-01-12',
            'date': '2025-01-12',
            'company_id': company.id,
            'intrastat_country_id': self.env.ref('base.be').id,
            'intrastat_transport_mode_id': self.env.ref('account_intrastat.account_intrastat_transport_1').id,
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'intrastat_transaction_id': self.env.ref('account_intrastat.account_intrastat_transaction_11').id,
                'quantity': 1,
                'price_unit': 400000000.0,
            })],
        }).action_post()
        contact = self.env['res.partner'].create({
            'name': 'Test Contact',
            'parent_id': company.partner_id.id,
            'type': 'other',
        })
        other_contact = self.env['res.partner'].create({
            'name': 'Other Contact',
            'parent_id': company.partner_id.id,
            'type': 'other',
        })
        account_return = self.env['account.return'].create({
            'name': 'INTRASTAT GOODS HU',
            'type_id': self.env.ref('l10n_hu_intrastat.hu_intrastat_goods_return_type').id,
            'company_id': company.id,
            'date_from': '2025-01-01',
            'date_to': '2025-01-31',
        })

        # Check report lines
        options = self._generate_options(self.report_goods, date_from='2025-01-01', date_to='2025-01-31')
        self.assertLinesValues(
            self.report_goods._get_lines(options),
            # 0:name, 1:system, 2:country, 3:transaction_code, 5:commodity_code, 6:origin country, 7:partner_vat, 12:value
            [                                            0,               1,         2,    3,          5,    6,              7,           12],
            [
                (                              'Intrastat',              '',        '',   '',         '',   '',             '', '400,000,000.00\xa0Ft'),
                ('Dispatch - BE0396779488 - 01063910 - BE', '19 (Dispatch)', 'Belgium', '11', '01063910', 'QV', 'BE0396779488', '400,000,000.00\xa0Ft'),
            ],
            options,
        )

        # Validate return
        account_return.refresh_checks()
        for check in account_return.check_ids.filtered(lambda c: c.result == 'todo'):
            check.result = 'reviewed'
        with self._patch_generate_locking_attachments():
            account_return.action_validate()

        with self.allow_pdf_render():
            action_records = account_return.with_user(user).action_submit()
        wizard = self.env[action_records['res_model']].with_user(user).with_context(action_records.get('context')).create({})

        # At first, no field is written on the company for the executive contact, so these fields should be empty
        self.assertFalse(wizard.l10n_hu_intrastat_contact_executive)
        self.assertFalse(wizard.l10n_hu_intrastat_contact_executive_status)
        # But as we created the wizard with 'user' the contact person field should be prefilled with his res.partner
        self.assertEqual(wizard.l10n_hu_intrastat_contact_person, user.partner_id)

        wizard.l10n_hu_intrastat_contact_executive = contact
        wizard.l10n_hu_intrastat_contact_executive_status = 'Manager'
        wizard.l10n_hu_intrastat_contact_person = other_contact

        # Error no mail, phone
        with self.assertRaises(ValidationError, msg="The contacts need a name, an email and a phone."):
            wizard.action_submit_contacts()

        contact.write({'email': 'test@test.test', 'phone': '+361234567'})
        other_contact.write({'email': 'other@test.test', 'phone': '+367654321'})

        # Since this user has no rights to write on company, executive contact fields should not be written on it
        wizard.with_user(user).action_submit_contacts()
        self.assertFalse(company.l10n_hu_intrastat_contact_executive)
        self.assertFalse(company.l10n_hu_intrastat_contact_executive_status)

        # Submit again but this time with rights, executive contact fields should be written on company
        action_records = wizard.with_user(self.env.user).action_submit_contacts()
        self.assertEqual(company.l10n_hu_intrastat_contact_executive, contact)
        self.assertEqual(company.l10n_hu_intrastat_contact_executive_status, 'Manager')

        options = account_return._get_closing_report_options()
        options['l10n_hu_intrastat_goods_submission_wizard_id'] = action_records['res_id']

        # Check file export
        file = self.report_handler.hu_intrastat_export_to_csv(options)
        self.assertEqual(
            file['file_content'],
            '{fejezet;sorrend};;;;;;;;;;;;;\n'
            '0;1;;;;;;;;;;;;;\n'
            ';;;;;;;;;;;;;;\n'
            '{MC01;M003_G;M003;MEV;MHO;JHNEV;JBEOSZTAS;JTELEFON;JEMAIL;KNEV;KTELEFON;KEMAIL;MEGJEGYZES;VGEA002}\n'
            f'2010;{company.vat};{company.vat};25;01;{contact.name};Manager;{contact.phone};{contact.email};{other_contact.name};{other_contact.phone};{other_contact.email};;\n'
            ';;;;;;;;;;;;;;\n'
            '{fejezet;sorrend};;;;;;;;;;;;;\n'
            '1;1;;;;;;;;;;;;;\n'
            ';;;;;;;;;;;;;;\n'
            '{T_SORSZ;TEKOD;UKOD;RTA;SZAORSZ;KGM;KIEGME;SZAOSSZ;STAERT;PADO};;;;;\n'
            f'1;01063910;11;{self.partner_a.country_code};{company.country_code};;1.0;400000000.0;400000000.0;{self.partner_a.vat};;;;;\n'
        )

        # Finally, if we open the wizard again the executive contact fields should be pre filled with company fields value
        with self.allow_pdf_render():
            action_records = account_return.action_submit()
        wizard = self.env[action_records['res_model']].with_user(user).with_context(action_records.get('context')).create({})

        self.assertEqual(wizard.l10n_hu_intrastat_contact_executive, company.l10n_hu_intrastat_contact_executive)
        self.assertEqual(wizard.l10n_hu_intrastat_contact_executive_status, company.l10n_hu_intrastat_contact_executive_status)
