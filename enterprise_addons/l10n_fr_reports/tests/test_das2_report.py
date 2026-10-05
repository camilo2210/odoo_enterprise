from odoo import Command
from odoo.exceptions import RedirectWarning
from odoo.tests import freeze_time, tagged, patch
from odoo.tools import file_open
from odoo.addons.l10n_fr_reports.tests.common import TestL10nFrReportsCommon


@freeze_time('2025-12-12')
@tagged('post_install_l10n', 'post_install', '-at_install')
class TestDAS2Report(TestL10nFrReportsCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref('l10n_fr_reports.account_report_l10n_fr_das2_report')

    def test_das2_report_engine(self):
        self._generate_move(amount=3000).action_post()
        self._generate_move(amount=2500).action_post()

        tag = self.env.ref('l10n_fr_reports.account_tag_das2_fees')

        options = self._generate_options()
        options['unfold_all'] = True

        report_lines = self.report._get_lines(options)
        self.assertLinesValues(
            report_lines,
            [0, 1],
            [
                ('DAS2 Report',               5500),
                (self.partner_a.display_name, 5500),
                (tag.display_name,            5500),
            ],
            options,
        )

    def test_das2_report_engine_no_data(self):
        options = self._generate_options()
        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            report_lines,
            [0, 1],
            [('DAS2 Report', 0)],
            options,
        )

    def test_das2_report_engine_threshold(self):
        options = self._generate_options()
        moves = (
            self._generate_move()
            + self._generate_move(partner=self.partner_b, amount=1000)
        )
        moves.action_post()

        report_lines = self.report._get_lines(options)
        self.assertLinesValues(
            report_lines,
            [0, 1],
            [
                ('DAS2 Report',               2401),
                (self.partner_a.display_name, 2401),
            ],
            options,
        )

    def test_das2_report_engine_irrelevant_accounts(self):
        options = self._generate_options()
        moves = (
            self._generate_move(account=self.company.expense_account_id, amount=5000)
            + self._generate_move(amount=3000, account=self.company.expense_account_id)
        )
        moves.action_post()

        report_lines = self.report._get_lines(options)
        self.assertLinesValues(
            report_lines,
            [0, 1],
            [('DAS2 Report', 0)],
            options,
        )

    def test_das2_report_engine_incomplete_partner(self):
        options = self._generate_options()
        self.partner_a.l10n_fr_profession_id = False
        move = self._generate_move()
        move.action_post()

        report_lines = self.report._get_lines(options)
        self.assertLinesValues(
            report_lines,
            [0, 1],
            [('DAS2 Report', 0)],
            options,
        )

    def test_das2_report_engine_multiple_tags(self):
        """ Test that we don't duplicate amounts when an account has multiple DAS2 tags. """
        das2_account_multiple_tags = self.env['account.account'].create({
            'name': 'Test Account Multiple Tags',
            'code': '424243',
            'tag_ids': [
                Command.link(self.env.ref('l10n_fr_reports.account_tag_das2_fees').id),
                Command.link(self.env.ref('l10n_fr_reports.account_tag_das2_commissions').id),
            ],
            'account_type': "expense_other",
        })
        move = self._generate_move(account=das2_account_multiple_tags)
        move.action_post()

        options = self._generate_options()
        report_lines = self.report._get_lines(options)

        self.assertLinesValues(
            report_lines,
            [0, 1],
            [
                ('DAS2 Report',               2401),
                (self.partner_a.display_name, 2401),
            ],
            options,
        )

    def test_check_required_fields_ok(self):
        """ All the requred fields are already configured in setUpClass, so this should just pass """
        handler = self.env['l10n_fr.das2.report.handler']

        partners = self.partner_a + self.partner_b
        contact_person = self.env.user

        handler._check_required_fields(partners, contact_person)

    def test_check_required_fields_all_errors_exhaustive(self):
        def assert_error(expected_msg):
            with self.assertRaises(RedirectWarning) as err:
                errors = handler._check_required_fields(partners, contact_person)
                handler._raise_required_fields_errors(errors)
            self.assertIn(expected_msg, str(err.exception))

        handler = self.env['l10n_fr.das2.report.handler']
        partners = self.partner_a + self.partner_b
        contact_person = self.env.user
        company_partner = self.env.company.partner_id
        firm = self.env.company.account_representative_id

        company_partner.l10n_fr_siret = False
        assert_error("company SIRET is not set")
        company_partner.l10n_fr_siret = "71204961800739"

        company_partner.street = False
        assert_error("company street address is not set")
        company_partner.street = "1 Enterprise Street"

        company_partner.zip = False
        assert_error("company zip code is not set")
        company_partner.zip = "75002"

        self.env.company.ape = False
        assert_error("company APE code is not set")
        self.env.company.ape = "6201Z"

        self.env.company.l10n_fr_das2_activity = False
        assert_error("company DAS2 activity is not set")
        self.env.company.l10n_fr_das2_activity = "Testing DAS2 Flows"

        company_partner.city = False
        assert_error("company city is not set")
        company_partner.city = "Paris"

        firm.l10n_fr_siret = False
        assert_error("account representative SIRET is not set")
        firm.l10n_fr_siret = "78467169500087"

        firm.street = False
        assert_error("account representative street address is not set")
        firm.street = "10 Business Ave"

        firm.zip = False
        assert_error("account representative zip code is not set")
        firm.zip = "75002"

        firm.city = False
        assert_error("account representative city is not set")
        firm.city = "Paris"

        cp_email = contact_person.email
        contact_person.email = False
        assert_error("point of contact email is not set")
        contact_person.email = cp_email

        cp_phone = contact_person.phone
        contact_person.phone = False
        assert_error("point of contact phone number is not set")
        contact_person.phone = cp_phone

        self.partner_a.street = False
        assert_error("partner 'partner_a' street address is not set")
        self.partner_a.street = "123 Main Street"

        self.partner_a.zip = False
        assert_error("partner 'partner_a' zip code is not set")
        self.partner_a.zip = "75001"

        self.partner_a.l10n_fr_siret = False
        assert_error("partner 'partner_a' SIRET is not set")
        self.partner_a.l10n_fr_siret = "50056940503239"

        profession = self.partner_a.l10n_fr_profession_id
        self.partner_a.l10n_fr_profession_id = False
        assert_error("partner 'partner_a' profession is not set")
        self.partner_a.l10n_fr_profession_id = profession

        self.partner_a.city = False
        assert_error("partner 'partner_a' city is not set")
        self.partner_a.city = "Paris"

        # Partner B is a non-French EU resident, so more checks apply
        self.partner_b.birth_date = False
        assert_error("partner 'partner_b' birth date is required for EU non-French residents")
        self.partner_b.birth_date = '1999-07-31'

        self.partner_b.city = False
        assert_error("partner 'partner_b' city is not set")
        self.partner_b.city = "Berlin"

    def test_edi_vals_generation_and_export(self):
        expected_file = file_open('l10n_fr_reports/tests/expected_files/DAS2_company_1_data_2025.xml', 'rb').read()
        self._generate_move(amount=3000).action_post()
        self._generate_move(partner=self.partner_b, amount=2500).action_post()
        self._generate_move(partner=self.partner_b, amount=2000, account=self.copyright_account).action_post()
        options = self._generate_options()
        wizard = self.env['l10n_fr.send.das2.report'].create({
            'year': options['date']['date_from'][:4],
        })

        mock_aspone_response = {
            'success': True,
            'data': {
                'insee_map': {
                    '75001': 'insee_code_75001',
                    'DE': 'insee_code_DE',
                },
            },
        }

        with patch.object(self.env.registry['account.report.async.document'], '_get_fr_webservice_answer', return_value=mock_aspone_response):
            self.assertDictEqual(
                self.env['l10n_fr.das2.report.handler']._prepare_edi_values(options, self.env.user.partner_id, 2025),
                {
                    'type': 'INFENT',
                    'declaration_type': 'HON',
                    'declaration_reference': 'INFENT000000000001',
                    'millesime': '26',
                    'is_test': '0',
                    'receiver': 'DGI_EDI_PART',
                    'contact_person': {
                        'name': 'Because I am accountman!',
                        'email': 'accountman@test.com',
                        'phone': '0123456789',
                    },
                    'writer': {
                        'identifier': '78467169500087',
                        'type': 'ENT_EDI_PART',
                        'designation':
                        'Test Firm',
                        'designation2': '',
                        'address': {
                            'street_number': '10',
                            'street_name': 'Business Ave',
                            'zip': '75002',
                            'country_code': 'FR',
                            'commune_name': 'Paris',
                        },
                        'reference': '78467169500087',
                    },
                    'debtor': {
                        'identifier': '71204961800739',
                        'designation': 'company_1_data',
                        'designation2': '',
                        'activity': 'Testing DAS2 Flows',
                        'ape': '6201Z',
                        'fiscal_year_end': '1231',
                        'address': {
                            'commune_name': 'Paris',
                            'country_code': 'FR',
                            'street_name': 'Enterprise Street',
                            'zip': '75002',
                            'street_number': '1',
                        },
                        'das2_codes': ['H', 'DA'],
                        'das2_totals_per_code': [5500, 2000],
                        'das2_global_totals': {
                            'benefits_in_kind': 0,
                            'indemnities_refunds': 0,
                            'withholding_tax': 0,
                        },
                        'dads_year': 2025,
                        'date_from': '20250101',
                        'date_to': '20251231',
                    },
                    'beneficiaries': [
                        {
                            'is_company': True,
                            'is_european': True,
                            'identifier': '50056940503239',
                            'designation': 'partner_a',
                            'designation2': '',
                            'address': {
                                'street_number': '123',
                                'street_type': '',
                                'street_name': 'Main Street',
                                'street2': '',
                                'commune_name': 'Paris',
                                'zip': '75001',
                                'country_code': 'FR',
                                'country_name': 'France',
                                'insee_zip': 'insee_code_75001',
                            },
                            'profession': 'Web developer',
                            'das2_codes': ['H'],
                            'das2_totals_per_code': [3000],
                            'das2_global_totals': {
                                'benefits_in_kind': 0,
                                'indemnities_refunds': 0,
                                'withholding_tax': 0,
                            },
                            'birth_date': '19990724',
                        },
                        {
                            'is_company': False,
                            'is_european': True,
                            'identifier': False,
                            'designation': 'partner_b',
                            'designation2': '',
                            'address': {
                                'street_number': '456',
                                'street_type': '',
                                'street_name': 'Side Street',
                                'street2': '',
                                'commune_name': 'Berlin',
                                'zip': '69001',
                                'country_code': 'DE',
                                'country_name': 'Germany',
                                'insee_country_code': 'insee_code_DE',
                            },
                            'profession': 'Marketing consultant',
                            'das2_codes': ['H', 'DA'],
                            'das2_totals_per_code': [2500, 2000],
                            'das2_global_totals': {
                                'benefits_in_kind': 0,
                                'indemnities_refunds': 0,
                                'withholding_tax': 0,
                            },
                            'birth_date': '19990731',
                        },
                    ],
                },
            )

            xml_file = wizard._export_das2_report()
            self.assertEqual(xml_file['file_name'], 'DAS2_company_1_data_2025.xml')
            self.assertEqual(xml_file['file_content'], expected_file)

    def test_format_phone_number(self):
        handler = self.env['l10n_fr.das2.report.handler']
        test_cases = [
            ('01 23 45 67 89', '0123456789'),
            ('+33 1 23 45 67 89', '0123456789'),
            ('0033 1 23 45 67 89', '0123456789'),
            ('(555) 123-4567', '5551234567'),
            ('1234567890', '1234567890'),
            (None, ''),
            ('', ''),
            ('abc', ''),
        ]

        for phone, expected in test_cases:
            with self.subTest(phone=phone):
                self.assertEqual(handler._format_phone_number(phone), expected)

    def test_send_das2_side_effects(self):
        wizard = self.env['l10n_fr.send.das2.report'].create({
            'year': '2025',
        })

        with patch.object(self.env.registry['l10n_fr.send.das2.report'], '_export_das2_report', return_value={
            'file_name': 'DAS2_company_1_data_2025.xml',
            'file_content': b'<xml>test</xml>',
        }), patch.object(self.env.registry['account.report.async.document'], '_get_fr_webservice_answer', return_value={
            'success': True,
            'data': {
                'deposit_id': 'test_deposit_id',
            },
        }) as mock_webservice:
            wizard.action_send_das2_report()
            mock_webservice.assert_called_once()

        async_export = self.env['account.report.async.document'].search([('name', '=', 'DAS2_company_1_data_2025.xml')])
        self.assertEqual(len(async_export), 1)
        self.assertEqual(async_export.attachment_name, 'DAS2_company_1_data_2025.xml')
        self.assertEqual(bytes(async_export.attachment), b'<xml>test</xml>')
        self.assertEqual(async_export.state, 'sent')
