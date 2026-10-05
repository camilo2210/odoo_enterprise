from unittest.mock import patch

from odoo import Command
from odoo.tests import tagged
from odoo.tools import mute_logger
from odoo.addons.account_reports.tests.common import TestAccountReportsCommon


@tagged('post_install_l10n', 'post_install', '-at_install')
class TestFrenchTaxClosing(TestAccountReportsCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestAccountReportsCommon.setup_country('fr_comp')
    def setUpClass(cls):
        super().setUpClass()

        cls.tax_20_g_purchase = cls.env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('name', '=', '20% G'), ('company_id', '=', cls.company.id)], limit=1)
        cls.tax_20_g_sale = cls.env['account.tax'].search([('type_tax_use', '=', 'sale'), ('name', '=', '20% G'), ('company_id', '=', cls.company.id)], limit=1)
        cls.tax_10_g_purchase = cls.env['account.tax'].search([('type_tax_use', '=', 'purchase'), ('name', '=', '10% G'), ('company_id', '=', cls.company.id)], limit=1)

        fr_return_type = cls.env.ref('l10n_fr_reports.vat_return_type')
        cls.return_payable_account = fr_return_type.with_company(cls.env.company).tax_payable_account_id
        cls.return_receivable_account = fr_return_type.with_company(cls.env.company).tax_receivable_account_id

        cls.report = cls.env.ref('l10n_fr_account.tax_report')
        cls.report_handler = cls.env[cls.report.custom_handler_model_name]

        cls.partner = cls.env['res.partner'].create({
            'name': 'A partner',
        })

        cls.company_data['company'].write({
            'vat': 'FR23334175221',
            'additional_identifiers': {'FR_SIRET': '40678483500521'},
            'phone': '555-555-5555',
            'email': 'test@example.com',
            'street': 'Rue du Souleillou',
            'street2': '2',
            'zip': '46800',
            'city': 'Montcuq',
        })

        cls.bank_partner = cls.env['res.partner.bank'].create({
            'partner_id': cls.env.company.partner_id.id,
            'account_number': 'FR3410096000508334859773Z27',
            'bank_name': 'French Bank',
            'bank_bic': 'SOGEFRPP',
            'allow_out_payment': True,
        })

        cls.env['ir.config_parameter'].sudo().set_str('l10n_fr_reports.aspone_mode', 'test')

    @classmethod
    def _get_move_create_data(cls, move_data, line_data):
        return {
            'partner_id': cls.partner.id,
            'invoice_date': '2024-04-15',
            'journal_id': cls.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [
                Command.create({
                    'name': 'Test',
                    'quantity': 1,
                    **line_data,
                })
            ],
            **move_data,
        }

    def test_fr_tax_closing_with_different_tax_groups(self):
        """ The aim of this test is testing a case where 2 tax groups are used, and we generate
            the tax closing entries for 2 periods.
            In the first period, we have 2 vendors bills, one using the first
            tax group and the other using the second one.
            We generate the tax closing entry and go to the next period.
            In the next period, we only have one invoice with a tax group
            similar to the first vendor bills.
            The tax closing entry for this period should have a line for the
            customer invoice and one for the amount carried from the previous period; both groups
            settle on the return's single pair.
        """
        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice'},
                line_data={'price_unit': 2000, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice'},
                line_data={'price_unit': 4000, 'tax_ids': [Command.link(self.tax_10_g_purchase.id)]}
            ),
        ])._post()

        april_return = self.env['account.return'].create({
            'name': "April return",
            'date_from': '2024-04-01',
            'date_to': '2024-04-30',
            'type_id': self.env.ref('l10n_fr_reports.vat_return_type').id,
            'company_id': self.env.company.id,
        })
        with self.allow_pdf_render():
            april_return.action_validate()

        self.assertRecordValues(
            april_return.closing_move_ids.line_ids,
            [
                {
                    'account_id': self.tax_20_g_purchase.repartition_line_ids.account_id.id,
                    'balance': -400,
                },
                {
                    'account_id': self.tax_10_g_purchase.repartition_line_ids.account_id.id,
                    'balance': -400,
                },
                {
                    'account_id': self.return_receivable_account.id,
                    'balance': 800,
                },
            ]
        )

        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice', 'invoice_date': '2024-05-15', 'journal_id': self.company_data['default_journal_sale'].id},
                line_data={'price_unit': 10000, 'tax_ids': [Command.link(self.tax_20_g_sale.id)]}
            ),
        ])._post()

        may_return = self.env['account.return'].create({
            'name': "May return",
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'type_id': self.env.ref('l10n_fr_reports.vat_return_type').id,
            'company_id': self.env.company.id,
        })
        with self.allow_pdf_render():
            may_return.action_validate()

        self.assertRecordValues(
            may_return.closing_move_ids.line_ids,
            [
                {
                    'account_id': self.tax_20_g_sale.repartition_line_ids.account_id.id,
                    'balance': 2000,
                },
                {
                    'account_id': self.return_receivable_account.id,
                    'balance': -800,
                },
                {
                    'account_id': self.return_payable_account.id,
                    'balance': -1200,
                },
            ]
        )

    def test_fr_send_edi_vat_values_vat_reimbursed_by_administration(self):
        """ The aim of this test is to verify edi VAT values
            once generated and when VAT should be reimbursed by
            the administration.
        """
        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-08', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 1000, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-09', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 667.5, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-12', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 3335, 'tax_ids': [Command.link(self.tax_10_g_purchase.id)]}
            ),
        ])._post()

        may_return = self.env['account.return'].create({
            'name': "May return",
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'type_id': self.env.ref('l10n_fr_reports.vat_return_type').id,
            'company_id': self.env.company.id,
        })

        with self.allow_pdf_render():
            send_vat_wizard_action = may_return.action_submit()
        send_vat_wizard = self.env[send_vat_wizard_action['res_model']].with_context(send_vat_wizard_action['context']).create({})
        send_vat_wizard.write({
            'bank_partner_id': self.bank_partner.id,
            'vat_amount': 667,
            'reimbursement_type': 'first_asking',
            'reimbursement_date': '2024-05-31',
            'is_reimbursement_comment': True,
            'reimbursement_comment': "Test reimbursement comment for may 2024.",
        })
        options = self._generate_options(
            self.report,
            date_from='2024-05-01',
            date_to='2024-05-31',
            default_options={
                'no_format': True,
                'unfold_all': True,
            }
        )
        lines = self.report._get_lines(options)
        edi_vals = send_vat_wizard._prepare_edi_vals(options, lines)

        values_to_check = [
            ('JA', '667,00'),  # VAT Credit
            ('HG', '667,00'),  # Total deductible
            ('JC', '667,00'),  # Total to carry forward
        ]

        for code, value in values_to_check:
            with self.subTest():
                self.assertIn(
                    {
                        'id': code,
                        'value': value,
                    },
                    edi_vals['declarations'][0]['forms'][0]['zones']
                )

        identif_zone_ids = {zone['id'] for zone in edi_vals['declarations'][0]['identif']['zones']}
        self.assertFalse(
            identif_zone_ids & {'GA', 'HA', 'KA'},
            "No telereglement zones must be emitted in the reimbursement case",
        )

        with patch.object(self.env.registry['l10n_fr_reports.send.vat.report'], '_send_xml_to_aspone', return_value=[]), \
             mute_logger("odoo.addons.base.models.ir_module", "odoo.tools.translate"):
            with self.allow_pdf_render():
                send_vat_wizard.send_vat_return()
            report_line_26 = self.env.ref('l10n_fr_account.tax_report_26_external')
            line_26_values = next(
                line for line in self.report._get_lines(options)
                if self.report._get_model_info_from_id(line.id) == ('account.report.line', report_line_26.id)
            )
            self.assertEqual(
                line_26_values.columns[0].name,
                '667.00',
                "The line 26 should be filled with the asked reimbursement amount",
            )

    def test_fr_send_edi_vat_values_vat_carry_over(self):
        """ The aim of this test is to verify edi VAT values
            once generated and when VAT is carry over for the
            next period.
        """
        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-08',
                           'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 1000, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-09', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 667.5, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-12', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 3335, 'tax_ids': [Command.link(self.tax_10_g_purchase.id)]}
            ),
        ])._post()

        send_vat_wizard = self.env['l10n_fr_reports.send.vat.report'].create({
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'report_id': self.report.id,
        })
        options = self._generate_options(
            self.report,
            date_from='2024-05-01',
            date_to='2024-05-31',
            default_options={
                'no_format': True,
                'unfold_all': True,
            }
        )
        lines = self.report._get_lines(options)
        edi_vals = send_vat_wizard._prepare_edi_vals(options, lines)

        values_to_check = [
            ('JA', '667,00'),  # VAT Credit
            ('HG', '667,00'),  # Total deductible
            ('JC', '667,00'),  # Total to carry forward
        ]

        for code, value in values_to_check:
            with self.subTest():
                self.assertIn(
                    {
                        'id': code,
                        'value': value,
                    },
                    edi_vals['declarations'][0]['forms'][0]['zones']
                )

        self.assertNotIn(
            {
                'id': 'GA',
                'iban': 'FR3410096000508334859773Z27',
                'bic': 'SOGEFRPP',
            },
            edi_vals['declarations'][0]['identif']['zones'],
        )
        self.assertNotIn(
            {
                'id': 'HA',
                'value': '667,00',
            },
            edi_vals['declarations'][0]['identif']['zones'],
        )
        self.assertNotIn(
            {
                'id': 'KA',
                'value': 'TVA1-20240501-20240531-3310CA3',
            },
            edi_vals['declarations'][0]['identif']['zones'],
        )

    def test_fr_send_edi_vat_values_vat_due_to_administration(self):
        """ The aim of this test is to verify edi VAT values
            once generated and when VAT is due to the administration.
        """
        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice', 'invoice_date': '2024-05-08', 'journal_id': self.company_data['default_journal_sale'].id},
                line_data={'price_unit': 1250, 'tax_ids': [Command.link(self.tax_20_g_sale.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice', 'invoice_date': '2024-05-09', 'journal_id': self.company_data['default_journal_sale'].id},
                line_data={'price_unit': 1250, 'tax_ids': [Command.link(self.tax_20_g_sale.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice', 'invoice_date': '2024-05-12', 'journal_id': self.company_data['default_journal_sale'].id},
                line_data={'price_unit': 1250, 'tax_ids': [Command.link(self.tax_20_g_sale.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'out_invoice', 'invoice_date': '2024-05-13', 'journal_id': self.company_data['default_journal_sale'].id},
                line_data={'price_unit': 1250, 'tax_ids': [Command.link(self.tax_20_g_sale.id)]}
            ),
        ])._post()

        send_vat_wizard = self.env['l10n_fr_reports.send.vat.report'].create({
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'report_id': self.report.id,
            'bank_partner_id': self.bank_partner.id,
            'vat_amount': 1000.0,
        })
        options = self._generate_options(
            self.report,
            date_from='2024-05-01',
            date_to='2024-05-31',
            default_options={
                'no_format': True,
                'unfold_all': True,
            }
        )
        lines = self.report._get_lines(options)
        edi_vals = send_vat_wizard._prepare_edi_vals(options, lines)

        values_to_check = [
            ('CA', '5000,00'),  # Taxable value
            ('FP', '5000,00'),  # Base 20%
            ('GP', '1000,00'),  # Tax 20%
            ('KA', '1000,00'),  # VAT Due
            ('GH', '1000,00'),  # Total gross VAT due
            ('ND', '1000,00'),  # Total net VAT due
            ('KE', '1000,00'),  # Total payable
        ]

        for code, value in values_to_check:
            with self.subTest():
                self.assertIn(
                    {
                        'id': code,
                        'value': value,
                    },
                    edi_vals['declarations'][0]['forms'][0]['zones']
                )

        self.assertIn(
            {
                'id': 'GA',
                'iban': 'FR3410096000508334859773Z27',
                'bic': 'SOGEFRPP',
            },
            edi_vals['declarations'][0]['identif']['zones'],
        )
        self.assertIn(
            {
                'id': 'HA',
                'value': '1000,00',
            },
            edi_vals['declarations'][0]['identif']['zones'],
        )
        self.assertIn(
            {
                'id': 'KA',
                'value': 'TVA1-20240501-20240531-3310CA3',
            },
            edi_vals['declarations'][0]['identif']['zones'],
        )

    def test_fr_send_empty_declaration_to_administration(self):
        """ The aim of this test is to verify edi VAT values
            when VAT is empty VS when not empty.
        """
        def get_edi_vals(start_date, end_date):
            send_vat_wizard = self.env['l10n_fr_reports.send.vat.report'].create({
                'date_from': start_date,
                'date_to': end_date,
                'report_id': self.report.id,
            })
            options = self._generate_options(
                self.report,
                date_from=start_date,
                date_to=end_date,
                default_options={
                    'no_format': True,
                    'unfold_all': True,
                }
            )
            lines = self.report._get_lines(options)
            return send_vat_wizard._prepare_edi_vals(options, lines)

        self.init_invoice('out_invoice', invoice_date='2024-05-08', amounts=[100], taxes=self.tax_20_g_sale, post=True)
        edi_vals_5 = get_edi_vals('2024-05-01', '2024-05-31')
        self.assertNotIn(
            {
                'id': 'KF',
                'value': 'X',
            },
            edi_vals_5['declarations'][0]['forms'][0]['zones'],
        )

        edi_vals_6 = get_edi_vals('2024-06-01', '2024-06-30')
        self.assertIn(
            {
                'id': 'KF',
                'value': 'X',
            },
            edi_vals_6['declarations'][0]['forms'][0]['zones'],
        )

    def test_fr_send_edi_vat_values_with_reimbursements(self):
        """ The aim of this test is to verify edi VAT export is created
            correctly when there are reimbursements not due.
        """

        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-09', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 667.5, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
        ])._post()

        # Create a VAT return for May in order to export EDI Report
        may_return = self.env['account.return'].create({
            'name': "May return",
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'type_id': self.env.ref('l10n_fr_reports.vat_return_type').id,
            'company_id': self.env.company.id,
        })
        send_vat_wizard = self.env['l10n_fr_reports.send.vat.report'].create({
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'report_id': self.report.id,
            'return_id': may_return.id,
            'bank_partner_id': self.bank_partner.id,
            'vat_amount': 667,
        })
        with self.allow_pdf_render():
            may_return.action_validate()

        # Mock the response from the ASPOne web service
        mock_aspone_response = {
            'xml_content': '',
            'success': True,
            'data': {
                'deposit_id': 'CCA7A30B-A69B-4C9B-8BFB-30DF435DABE9',
            },
        }

        with patch.object(self.env.registry['account.report.async.document'], '_get_fr_webservice_answer', return_value=mock_aspone_response), \
             mute_logger("odoo.addons.base.models.ir_module", "odoo.tools.translate"):
            with self.allow_pdf_render():
                send_vat_wizard.send_vat_return()

            self.assertEqual(len(send_vat_wizard.report_async_document_ids), 2)

            export = self.env['account.report.async.export'].search([
                ('date_from', '=', send_vat_wizard.date_from),
                ('date_to', '=', send_vat_wizard.date_to),
                ('report_id', '=', self.env.ref('l10n_fr_account.tax_report').id),
            ])

            export.ensure_one()

            self.assertEqual(export.document_ids, send_vat_wizard.report_async_document_ids)
            self.assertEqual(export.state, 'sent')

            export.document_ids[0].state = 'accepted'
            self.assertEqual(export.state, 'mixed')
            export.document_ids[1].state = 'accepted'
            self.assertEqual(export.state, 'accepted')

    def test_fr_send_edi_vat_values_with_carryover_reimbursements(self):
        """ The aim of this test is to verify carryover reimboursement move
            in correctly created when we have an unclaimed tax amount carried to the
            next month.
        """

        self.env['account.move'].create([
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-05-09', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 10000, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
            self._get_move_create_data(
                move_data={'move_type': 'in_invoice', 'invoice_date': '2024-06-09', 'journal_id': self.company_data['default_journal_purchase'].id},
                line_data={'price_unit': 23000, 'tax_ids': [Command.link(self.tax_20_g_purchase.id)]}
            ),
        ])._post()

        # Create a VAT return for May in order to have VAT amount to carry over to the next month
        may_return = self.env['account.return'].create({
            'name': "May return",
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'type_id': self.env.ref('l10n_fr_reports.vat_return_type').id,
            'company_id': self.env.company.id,
        })
        self.env['l10n_fr_reports.send.vat.report'].create({
            'date_from': '2024-05-01',
            'date_to': '2024-05-31',
            'report_id': self.report.id,
            'return_id': may_return.id,
        })
        with self.allow_pdf_render():
            may_return.action_validate()

        june_return = self.env['account.return'].create({
            'name': "May return",
            'date_from': '2024-06-01',
            'date_to': '2024-06-30',
            'type_id': self.env.ref('l10n_fr_reports.vat_return_type').id,
            'company_id': self.env.company.id,
        })
        send_vat_wizard_june = self.env['l10n_fr_reports.send.vat.report'].create({
            'date_from': '2024-06-01',
            'date_to': '2024-06-30',
            'report_id': self.report.id,
            'return_id': june_return.id,
            'bank_partner_id': self.bank_partner.id,
            'vat_amount': 6600,
        })
        with self.allow_pdf_render():
            june_return.action_validate()

        # Mock the response from the ASPOne web service
        mock_aspone_response = {
            'xml_content': '',
            'success': True,
            'data': {
                'deposit_id': 'CCA7A30B-A69B-4C9B-8BFB-30DF435DABE9',
            },
        }

        original_create_carryover_reimbursment_move = send_vat_wizard_june._create_carryover_reimbursment_move
        captured_moves = []

        def _create_carryover_reimbursment_move(obj, *args):
            result = original_create_carryover_reimbursment_move(*args)
            captured_moves.append(result.id)
            return result

        with patch.object(self.env.registry['account.report.async.document'], '_get_fr_webservice_answer', return_value=mock_aspone_response), \
             patch.object(self.env.registry['l10n_fr_reports.send.vat.report'], '_create_carryover_reimbursment_move', autospec=True, side_effect=_create_carryover_reimbursment_move), \
             self.allow_pdf_render(), \
             mute_logger("odoo.addons.base.models.ir_module", "odoo.tools.translate"):
            send_vat_wizard_june.send_vat_return()

        carryover_reimboursement_move = self.env['account.move'].browse(captured_moves)
        self.assertRecordValues(carryover_reimboursement_move.line_ids, [
            {'account_id': self.return_receivable_account.id, 'balance': -6600.00},
            {'account_id': self.env['account.chart.template'].ref('pcg_44583').id, 'balance': 6600.00},
        ])
