# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
from contextlib import ExitStack, contextmanager, nullcontext
from unittest import SkipTest, mock
from unittest.mock import patch

from odoo import modules
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase, freeze_time, tagged
from odoo.tools import file_open

from .mocked_invoice_response import generate_response
from .mocked_credit_note_response import generate_response as credit_note_generate_response
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_br_avatax.models.account_external_tax_mixin import (
    AccountExternalTaxMixin,
)

_logger = logging.getLogger(__name__)

DUMMY_SANDBOX_ID = "DUMMY_ID"
DUMMY_SANDBOX_KEY = "DUMMY_KEY"
TEST_DATETIME = "2025-02-05T22:55:17+00:00"


class TestBRMockedRequests(TransactionCase):
    @classmethod
    def setUpClass(self):
        super().setUpClass()
        # Any additional patches that need to be applied for the tests can be added here.
        self.mocked_l10n_br_iap_patches = []

    @contextmanager
    def _with_mocked_l10n_br_iap_request(self, expected_communications):
        """Checks that we send the right requests and returns corresponding mocked responses. Heavily inspired by
        patch_session in l10n_ke_edi_oscu."""
        module = self.test_module
        self.maxDiff = None
        test_case = self
        json_module = json
        expected_communications = iter(expected_communications)

        def mocked_l10n_br_iap_request(self, route, company, json=None):
            edi_installed = self.env['ir.module.module']._get('l10n_br_edi').state == 'installed'

            def replace_ignore(dict_to_replace):
                """Replace `___ignore___` in the expected request JSONs by unittest.mock.ANY,
                which is equal to everything. In addition, itemCode is always added to all tax
                requests if l10n_br_edi is installed. This means that a test case could pass with
                a specific file if only l10n_br_avatax is installed but fail if l10n_br_edi
                is also installed (or vise versa). As such, we skip it if edi is not installed that
                way we don't need to duplicate input files."""
                new_dict = {}
                for k, v in dict_to_replace.items():
                    if k == 'itemCode' and not edi_installed:
                        continue
                    if v == "___ignore___":
                        v = mock.ANY
                    new_dict[k] = v
                return new_dict

            expected_route, expected_request_filename, expected_response_filename = next(expected_communications)
            test_case.assertEqual(route, expected_route)
            with file_open(f"{module}/tests/mocked_requests/{expected_request_filename}.json", "r") as request_file:
                expected_request = json_module.loads(request_file.read(), object_hook=replace_ignore)
                test_case.assertEqual(
                    json,
                    expected_request,
                    f"Expected request did not match actual request for route {route}.",
                )

            with file_open(f"{module}/tests/mocked_responses/{expected_response_filename}.json", "r") as response_file:
                api_response = json_module.loads(response_file.read())

                if expected_route == "calculate_tax":
                    expected_lines = api_response["lines"]

                    # Generically get line information for any record type that supports the
                    # account.external.tax.mixin.
                    record_model, record_id = json['header']['documentCode'].split('_')
                    record = self.env[record_model].browse(int(record_id))
                    lines = [
                        line['base_line']['record']
                        for line in record._get_external_tax_service_params()['line_data']
                    ]

                    test_case.assertEqual(
                        len(lines), len(expected_lines), f"The sent record was expected to have {len(expected_lines)} lines.",
                    )

                    # Set the line IDs in the mocked response to the line IDs of this records.
                    for i, line in enumerate(expected_lines):
                        line["lineCode"] = lines[i].id

                return api_response

        with ExitStack() as patch_stack:
            patch_stack.enter_context(patch(
                f"{AccountExternalTaxMixin.__module__}.AccountExternalTaxMixin._l10n_br_iap_request",
                autospec=True,
                side_effect=mocked_l10n_br_iap_request,
            ))
            # Apply all other patches in addition to the required ones.
            for other_patch in self.mocked_l10n_br_iap_patches:
                patch_stack.enter_context(other_patch)
            yield

        if next(expected_communications, None):
            self.fail("Not all expected calls were made!")


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrCommon(AccountTestInvoicingCommon, TestBRMockedRequests):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('br')
    def setUpClass(cls):
        res = super().setUpClass()
        cls._setup_credentials()
        cls.foreign_currency = cls.setup_other_currency('EUR')
        cls.fp_avatax = cls.env['account.fiscal.position'].create({
            'name': 'Avatax Brazil',
            'l10n_br_is_avatax': True,
        })

        cls._setup_partners()

        # Ensure the IAP service exists for this company. Otherwise, iap.account's get() method will fail.
        iap_service = cls.env.ref('l10n_br_avatax.iap_service_br_avatax')
        cls.env['iap.account'].create(
            {
                'service_id': iap_service.id,
                'company_ids': [(6, 0, cls.company_data['company'].ids)],
            }
        )

        cls._setup_products()

        return res

    @classmethod
    def _setup_credentials(cls):
        # Set real credentials here to run the integration tests
        cls.env.company.l10n_br_avatax_api_identifier = DUMMY_SANDBOX_ID
        cls.env.company.l10n_br_avatax_api_key = DUMMY_SANDBOX_KEY
        cls.env.company.l10n_br_avalara_environment = 'sandbox'

    @classmethod
    def _setup_partners(cls):
        company = cls.company_data['company']
        company.write({
            'street': 'Rua Marechal Deodoro 630',
            'street2': 'Edificio Centro Comercial Itália 24o Andar',
            'city': 'Curitiba',
            'state_id': cls.env.ref('base.state_br_pr').id,
            'country_id': cls.env.ref('base.br').id,
            'zip': '80010-010',
        })
        company.partner_id.write({
            'l10n_br_tax_regime': 'individual',
            'vat': '49233848000150',
        })

        cls.partner = cls.env['res.partner'].create({
            'name': 'Avatax Brazil Test Partner',
            'street': 'Avenida SAP, 188',
            'street2': 'Cristo Rei',
            'city': 'São Leopoldo',
            'state_id': cls.env.ref('base.state_br_rs').id,
            'country_id': cls.env.ref('base.br').id,
            'zip': '93022-718',
            'property_account_position_id': cls.fp_avatax.id,
            'l10n_br_tax_regime': 'individual',
            'additional_identifiers': {'BR_CN': '92355690448'},
        })

        cls.foreign_partner = cls.env['res.partner'].create({
            'name': 'Foreign Partner',
            'street': '77 Santa Barbara Rd',
            'city': 'Pleasant Hill',
            'state_id': cls.env.ref('base.state_us_5').id,
            'country_id': cls.env.ref('base.us').id,
            'zip': '94523',
            'property_account_position_id': cls.fp_avatax.id,
            'l10n_br_tax_regime': 'notApplicable',
            'l10n_br_taxpayer': 'non',
            'l10n_br_subject_cofins': 'N',
            'l10n_br_subject_pis': 'N',
        })

        cls.partner_shipping_id = cls.env['res.partner'].create({
            'type': 'delivery',
            'street_name': 'Avenida Europa',
            'street_number': '2048',
            'street2': 'Jardim São Domingos',
            'state_id': cls.env.ref('base.state_br_sp').id,
            'city_id': cls.env.ref('l10n_br.city_br_124').id,
            'country_id': cls.env.ref('base.br').id,
            'city': 'Americana',
        })

    @classmethod
    def _setup_products(cls):
        common = {
            'l10n_br_ncm_code_id': cls.env.ref('l10n_br_avatax.49011000').id,
            'l10n_br_source_origin': '0',
            'l10n_br_sped_type': 'FOR PRODUCT',
            'l10n_br_use_type': 'use or consumption',
            'supplier_taxes_id': None,
        }

        cls.product = cls.env['product.product'].create({
            'name': 'Product',
            'default_code': 'PROD1',
            'barcode': '123456789',
            'list_price': 15.00,
            'standard_price': 15.00,
            **common,
        })
        cls.product_user = cls.env['product.product'].create({
            'name': 'Odoo User',
            'list_price': 35.00,
            'standard_price': 35.00,
            **common,
        })
        cls.product_user_discount = cls.env['product.product'].create({
            'name': 'Odoo User Initial Discount',
            'list_price': -5.00,
            'standard_price': -5.00,
            **common,
        })
        cls.product_accounting = cls.env['product.product'].create({
            'name': 'Accounting',
            'list_price': 30.00,
            'standard_price': 30.00,
            **common,
        })
        cls.product_expenses = cls.env['product.product'].create({
            'name': 'Expenses',
            'list_price': 15.00,
            'standard_price': 15.00,
            **common,
        })
        cls.product_invoicing = cls.env['product.product'].create({
            'name': 'Invoicing',
            'list_price': 15.00,
            'standard_price': 15.00,
            **common,
        })

    @classmethod
    @contextmanager
    def _skip_no_credentials(cls):
        company = cls.env.company
        if company.l10n_br_avatax_api_identifier == DUMMY_SANDBOX_ID or \
           company.l10n_br_avatax_api_key == DUMMY_SANDBOX_KEY or \
           company.l10n_br_avalara_environment != 'sandbox':
            raise SkipTest('no Avalara credentials')
        yield

    @classmethod
    @contextmanager
    def _capture_request_br(cls, return_value=None):
        with patch(f'{AccountExternalTaxMixin.__module__}.AccountExternalTaxMixin._l10n_br_iap_request', return_value=return_value) as mocked:
            yield mocked

    @classmethod
    @freeze_time('2021-01-01')
    def _create_invoice_01_and_expected_response(cls, move_type='out_invoice'):
        invoice = cls._create_invoice(
            move_type=move_type,
            partner_id=cls.partner,
            fiscal_position_id=cls.fp_avatax,
            invoice_line_ids=[
                cls._prepare_invoice_line(product_id=cls.product_user, discount=10),
                cls._prepare_invoice_line(product_id=cls.product_accounting),
                cls._prepare_invoice_line(product_id=cls.product_expenses),
                cls._prepare_invoice_line(product_id=cls.product_invoicing),
            ],
        )
        return invoice, generate_response(invoice.invoice_line_ids)

    @classmethod
    @freeze_time('2021-01-01')
    def _create_invoice_02(cls, operation_types=None):
        operation_types = operation_types or (
            cls.env.ref('l10n_br_avatax.operation_type_1'),
            cls.env.ref('l10n_br_avatax.operation_type_2'),
            cls.env.ref('l10n_br_avatax.operation_type_3'),
            cls.env.ref('l10n_br_avatax.operation_type_60'),
        )
        return cls._create_invoice(
            partner_id=cls.partner,
            fiscal_position_id=cls.fp_avatax,
            invoice_line_ids=[
                cls._prepare_invoice_line(product_id=cls.product_user, l10n_br_goods_operation_type_id=operation_types[0]),
                cls._prepare_invoice_line(product_id=cls.product_accounting, l10n_br_goods_operation_type_id=operation_types[1]),
                cls._prepare_invoice_line(product_id=cls.product_expenses, l10n_br_goods_operation_type_id=operation_types[2]),
                cls._prepare_invoice_line(product_id=cls.product_invoicing, l10n_br_goods_operation_type_id=operation_types[3]),
            ],
        )

    @classmethod
    def _create_invoice_03(cls):
        # Create Export of Goods Invoice
        cls.product.barcode = False
        invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': cls.foreign_partner.id,
            'fiscal_position_id': cls.fp_avatax.id,
            'invoice_date': '2025-10-20',
            'invoice_date_due': '2025-10-21',
            'invoice_line_ids': [
                Command.create({
                    'product_id': cls.product.id,
                    'tax_ids': None,
                    'price_unit': cls.product.list_price,
                })
            ],
            'incoterm_location': 'testincotermlocationtestincotermlocationtestincotermlocationtestincoterm',
            'l10n_br_shipping_state_id': cls.env.ref('base.state_br_ac').id
        })

        return invoice

    @classmethod
    def _create_invoice_with_diff_partner_shipping(cls):
        invoice = cls._create_invoice_02(operation_types=(False, ) * 4)
        # Create a delivery address for partner
        partner_shipping_id = cls.partner_shipping_id
        invoice.partner_id.write({
            'child_ids': [Command.link(partner_shipping_id.id)],
            'l10n_br_tax_regime': 'realProfit',
            'city_id': cls.env.ref("l10n_br.city_br_002"),
        })
        # Default document type is NF-e
        invoice.write({
            'invoice_date': TEST_DATETIME,
            'l10n_latam_document_type_id': cls.env.ref('l10n_br.dt_55').id,
            'l10n_br_cnae_code_id': cls.env.ref("l10n_br_avatax.cnae_6209100").id,
            'partner_shipping_id': partner_shipping_id.id
        })
        return invoice


class TestAvalaraBrInvoiceCommon(TestAvalaraBrCommon):
    _test_user_groups = None  # FIXME list needed groups

    def assertInvoice(self, invoice, test_exact_response):
        self.assertEqual(
            len(invoice.invoice_line_ids.tax_ids),
            0,
            'There should be no tax rate on the line.'
        )

        self.assertRecordValues(invoice, [{
            'amount_total': 91.50,
            'amount_untaxed': 91.50,
            'amount_tax': 0.0,
        }])

        # When the external tests run this will need to do an IAP request which isn't possible in testing mode, see:
        # 7416acc111793ac1f7fd0dc653bb05cf7af28ebe
        with patch.object(modules.module, 'current_test', False) if 'external_l10n' in self.test_tags else nullcontext():
            invoice.action_post()

        if test_exact_response:
            expected_amounts = {
                'amount_total': 91.50,
                'amount_untaxed': 91.50 - 10.98 - 5.02,
                'amount_tax': 10.98 + 5.02,
            }
            self.assertRecordValues(invoice, [expected_amounts])

            self.assertEqual(invoice.tax_totals['total_amount_currency'], expected_amounts['amount_total'])
            self.assertEqual(invoice.tax_totals['base_amount_currency'], expected_amounts['amount_untaxed'])

            self.assertEqual(len(invoice.tax_totals['subtotals']), 1)
            self.assertEqual(invoice.tax_totals['subtotals'][0]['base_amount_currency'], expected_amounts['amount_untaxed'])

            avatax_mapping = {avatax_line['lineCode']: avatax_line for avatax_line in test_exact_response['lines']}
            for line in invoice.invoice_line_ids:
                avatax_line = avatax_mapping[line.id]
                self.assertEqual(
                    line.price_total,
                    avatax_line['lineAmount'] - avatax_line['lineTaxedDiscount'],
                    f"Tax-included price doesn't match tax returned by Avatax for line {line.id} (product: {line.product_id.display_name})."
                )
                self.assertAlmostEqual(
                    line.price_subtotal,
                    avatax_line['lineNetFigure'] - avatax_line['lineTaxedDiscount'],
                    msg=f'Wrong Avatax amount for {line.id} (product: {line.product_id.display_name}), there is probably a mismatch between the test SO and the mocked response.'
                )

        else:
            for line in invoice.invoice_line_ids:
                product_name = line.product_id.display_name
                self.assertGreater(len(line.tax_ids), 0, 'Line with %s did not get any taxes set.' % product_name)

            self.assertGreater(invoice.amount_tax, 0.0, 'Invoice has a tax_amount of 0.0.')


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrInvoice(TestAvalaraBrInvoiceCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_01_invoice_br(self):
        invoice, response = self._create_invoice_01_and_expected_response()
        with self._capture_request_br(return_value=response):
            self.assertInvoice(invoice, test_exact_response=response)

    def test_02_non_brl(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.currency_id = self.env.ref('base.USD')

        # We don't want to use assertRaisesRegex because we don't want to rollback (simulate the commit)
        try:
            self.assertInvoice(invoice, test_exact_response=None)
            self.fail("Should raise a UserError before")
        except UserError as e:
            self.assertRegex(str(e), r'.* Brazilian Real is required to calculate taxes with Avatax.')

    def test_03_transport_cost(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        transport_cost_products = self.env['product.product'].create([{
            'name': 'freight',
            'list_price': 10.00,
            'l10n_br_transport_cost_type': 'freight',
        }, {
            'name': 'insurance',
            'list_price': 20.00,
            'l10n_br_transport_cost_type': 'insurance',
        }, {
            'name': 'other',
            'list_price': 30.00,
            'l10n_br_transport_cost_type': 'other',
        }])

        for product in transport_cost_products:
            self.env['account.move.line'].create({
                'product_id': product.id,
                'price_unit': product.list_price,
                'move_id': invoice.id,
            })

        # (line amount, freight, insurance, other) per line
        expecteds = [
            (35.00, 3.68, 7.37, 11.05),
            (30.00, 3.16, 6.32, 9.47),
            (15.00, 1.58, 3.16, 4.74),
            (15.00, 1.58, 3.15, 4.74), # note that the insurance amount is different from the line above to ensure the total adds up to 20
        ]

        api_request = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        actual_lines = api_request['lines']
        self.assertEqual(len(expecteds), len(actual_lines), 'Different amount of expected and actual lines.')

        for expected, line in zip(expecteds, actual_lines):
            amount, freight, insurance, other = expected
            self.assertEqual(amount, line['lineAmount'])
            self.assertEqual(freight, line['freightAmount'])
            self.assertEqual(insurance, line['insuranceAmount'])
            self.assertEqual(other, line['otherCostAmount'])

    def test_05_credit_note(self):
        """Tax calculation without setting operation types on the lines. This should use the default
            from the parent model instead. (salesReturn)
        """
        invoice, response = self._create_invoice_01_and_expected_response()
        with self._capture_request_br(return_value=response):
            invoice.action_post()

        credit_note_wizard = self.env['account.move.reversal'].with_context(active_model='account.move', active_ids=invoice.ids).create({
            'journal_id': invoice.journal_id.id,
        })
        credit_note_wizard.reverse_moves()

        credit_note = self.env['account.move'].search([('reversed_entry_id', '=', invoice.id)])
        self.assertTrue(credit_note, "A credit note should have been created.")

        payload = credit_note._prepare_l10n_br_avatax_document_service_call(credit_note._get_l10n_br_avatax_service_params())
        self.assertTrue(all(line['operationType'] == 'salesReturn' for line in payload['lines']), 'The default operationType for credit notes should be salesReturn.')
        self.assertEqual(payload['header']['invoicesRefs'][0]['documentCode'], f'account.move_{invoice.id}', 'The credit note should reference the original invoice.')

    def test_06_unique_operation_types(self):
        """Tax calculation with unique operation types on each line."""
        invoice = self._create_invoice_02()
        self.assertRecordValues(invoice, [{
            'amount_total': 95.0,
            'amount_untaxed': 95.0,
            'amount_tax': 0.0,
        }])

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        operation_types = [line['operationType'] for line in payload['lines']]
        expected_operation_types = ['standardSales', 'complementary', 'amountComplementary', 'salesReturn']
        self.assertEqual(operation_types, expected_operation_types, 'The expected operation types are not properly set. It should be unique per line.')

    def test_07_override_operation_type(self):
        """Tax calculation with operation types set only on a single line. The rest should default to standardSales."""
        operation_types = (
            False,
            self.env.ref('l10n_br_avatax.operation_type_2'),
            False,
            False,
        )

        invoice = self._create_invoice_02(operation_types=operation_types)
        self.assertRecordValues(invoice, [{
            'amount_total': 95.0,
            'amount_untaxed': 95.0,
            'amount_tax': 0.0,
        }])

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        operation_types = [line['operationType'] for line in payload['lines']]
        expected_operation_types = ['standardSales', 'complementary', 'standardSales', 'standardSales']
        self.assertEqual(operation_types, expected_operation_types, 'The expected operation types are not properly set.')

    def test_08_vendor_bill(self):
        """ Verify the differences between sending an invoice and a bill. """
        bill, response = self._create_invoice_01_and_expected_response(move_type='in_invoice')
        bill.l10n_latam_document_number = '1'
        self.assertEqual(
            bill.l10n_br_goods_operation_type_id,
            self.env.ref('l10n_br_avatax.operation_type_59'),
            "Default operation type for bills should be standardPurchase."
        )

        with self._capture_request_br(return_value=response) as patched:
            bill.action_post()

        payload = patched.call_args.args[2]
        self.assertEqual(
            payload['header']['operationType'],
            'standardPurchase',
            'The operationType for vendor bills should be standardPurchase.'
        )

    def test_09_ex_citation_in_payload(self):
        """ Ensure that the 'ex' citation from the NCM code is included in the Avatax API payload. """
        self.env.ref('l10n_br_avatax.49011000').write({'ex': '001'})
        invoice, _ = self._create_invoice_01_and_expected_response()
        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        line = payload['lines'][0]
        self.assertEqual(line['itemDescriptor']['ex'], '001', "EX field should match the value set in NCM code")

    def test_10_tax_calculation_api_error(self):
        invoice, _ = self._create_invoice_01_and_expected_response()
        response = {
            "error": {
                "code": "TC000",
                "message": "Errors: ",
                "innerError": [
                    {
                        "code": "TC001",
                        "message": "Cannot find TaxCitation based on NCM for PIS",
                        "lineCode": invoice.invoice_line_ids.ids[0],
                        "where": {
                            "type": "PIS",
                            "hsCodes.codeType": "NCM",
                            "hsCodes.code": "49011000",
                            "date": "2025-07-18T00:00:00.000Z",
                        },
                        "lineIndex": 0,
                        "itemCode": "false",
                    },
                ],
            }
        }

        with self._capture_request_br(return_value=response), \
             self.assertRaisesRegex(UserError, "Cannot find TaxCitation based on NCM for PIS"):
            invoice.button_external_tax_calculation()

    @freeze_time(TEST_DATETIME)
    def test_11_service_invoice(self):
        """ Make sure that service invoices are handled correctly and can have CNAE overriden. """
        rio_city = self.env.ref("l10n_br.city_br_002")
        invoice = self._create_invoice_02(operation_types=(False, ) * 4)
        invoice.invoice_line_ids.mapped('product_id').write(
            {
                "type": "service",
                "l10n_br_property_service_code_origin_id": self.env["l10n_br.service.code"].create(
                    {"code": "12345", "city_id": rio_city.id},
                ),
            },
        )

        invoice.write({
            'invoice_date': TEST_DATETIME,
            'l10n_latam_document_type_id': self.env.ref('l10n_br.dt_SE').id,
            'l10n_br_cnae_code_id': self.env.ref("l10n_br_avatax.cnae_6209100").id,
        })
        invoice.partner_id.city_id = rio_city

        ncm_code_id = self.env.ref('l10n_br_avatax.49021000')
        ncm_code_id.l10n_br_cnae_code_id = self.env.ref('l10n_br_avatax.cnae_6204000')
        invoice.invoice_line_ids[-1].product_id.l10n_br_ncm_code_id = ncm_code_id

        with self._with_mocked_l10n_br_iap_request([
            ("calculate_tax", "anonymous_tax_request", "anonymous_tax_response"),
        ]):
            invoice.action_post()

        self.assertRecordValues(invoice, [{
            'amount_total': 95.0,
            'amount_untaxed': 95.0,
            'amount_tax': 0.0,
        }])

    def test_12_service_invoice_with_installments(self):
        """Test that service invoices with installments clear tax info when using Avalara. It's necessary because Avalara
        expects installments to be sent without taxes for service invoices."""
        invoice, response = self._create_invoice_01_and_expected_response()
        rio_city = self.env.ref("l10n_br.city_br_002")

        invoice.invoice_payment_term_id = self.pay_terms_b.id
        invoice.l10n_latam_document_type_id = self.env.ref("l10n_br.dt_SE").id
        invoice.partner_id.city_id = rio_city

        # Mark all products as services and assign service code
        for line in invoice.invoice_line_ids:
            line.tax_ids = self.tax_sale_a
            line.product_id.write({
                'type': 'service',
                'l10n_br_property_service_code_origin_id': self.env['l10n_br.service.code'].create({
                    'code': '12345',
                    'city_id': rio_city.id,
                }),
            })

        # Ensure there's a tax amount
        self.assertGreater(invoice.amount_tax, 0, "There should be a tax amount on this invoice.")

        with self._capture_request_br(return_value=response) as captured:
            invoice.button_external_tax_calculation()

        payload = captured.call_args.args[2]

        with self._capture_request_br(return_value=response) as captured:
            invoice.button_external_tax_calculation()

        self.assertEqual(payload, captured.call_args.args[2], "The payload of the second call should be the same")

    def test_11_service_invoice_with_discount(self):
        invoice, response = self._create_invoice_01_and_expected_response()
        invoice.invoice_line_ids.product_id.type = 'service'
        invoice.l10n_latam_document_type_id = self.env.ref('l10n_br.dt_SE')
        invoice.partner_id.city_id = self.env.ref('l10n_br.city_br_001')

        with self._capture_request_br(return_value=response):
            invoice.action_post()

        self.assertEqual(
            invoice.invoice_line_ids[0].price_total,
            35.0,
            "The discount shouldn't have been subtracted, it's already accounted for in lineNetFigure."
        )

    def test_13_export_goods_invoice(self):
        """ Test that export for goods invoices are sent to Avalara with the required information"""
        invoice = self._create_invoice_03()
        with self._with_mocked_l10n_br_iap_request([
            ("calculate_tax", "nfe_export_goods_tax_request", "nfe_export_goods_tax_response"),
        ]):
            invoice.action_post()

    def test_14_service_invoice_with_rendered_address(self):
        rio_city = self.env.ref("l10n_br.city_br_002")
        ncm_code_id = self.env.ref('l10n_br_avatax.service_1_07')
        # Make a service invoice
        invoice = self._create_invoice_with_diff_partner_shipping()
        invoice.l10n_latam_document_type_id = self.env.ref('l10n_br.dt_SE').id
        # Configure the product to be a service type for rendered address
        invoice.invoice_line_ids.mapped('product_id').write(
            {
                "type": "service",
                "l10n_br_property_service_code_origin_id": self.env["l10n_br.service.code"].create(
                    {"code": "1.07", "city_id": rio_city.id},
                ),
                "l10n_br_ncm_code_id": ncm_code_id,
            },
        )

        with self._with_mocked_l10n_br_iap_request([
            ("calculate_tax", "nfse_rendered_address_request", "nfse_rendered_address_response"),
        ]):
            invoice.action_post()

    def test_14_goods_invoice_with_delivery_address(self):
        invoice = self._create_invoice_with_diff_partner_shipping()
        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        delivery = payload['header']['locations'].get('delivery')
        self.assertTrue(delivery, "Delivery address should be sent in request when partner_shipping_id is not the same as partner_id")

    @freeze_time(TEST_DATETIME)
    def test_mock_calculate_tax_with_negative_lines(self):
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_invoice_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_invoice_line(product_id=self.product_user, price_unit=10.0),
                self._prepare_invoice_line(product_id=self.product_user_discount, price_unit=-60.0),
            ],
            post=False,
        )
        with self._with_mocked_l10n_br_iap_request(
            [('calculate_tax', 'tax_request_negative_lines', 'tax_response_negative_lines')]
        ):
            invoice.action_post()

        self.assertRecordValues(invoice.invoice_line_ids, [
            {'price_unit': 100.0, 'price_subtotal': 88.0, 'price_total': 100.0},
            {'price_unit': 50.0, 'price_subtotal': 44.0, 'price_total': 50.0},
            {'price_unit': 10.0, 'price_subtotal': 8.8, 'price_total': 10.0},
            {'price_unit': -60.0, 'price_subtotal': -52.8, 'price_total': -60.0},
        ])

    def test_redistribute_amounts_after_api_call(self):
        """Test that _process_external_taxes correctly distributes tax values back to all invoice lines."""
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_invoice_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_invoice_line(product_id=self.product_user_discount, price_unit=-30.0),
            ],
        )

        service_params = invoice._get_l10n_br_avatax_service_params()
        line_data_list = service_params['line_data']
        self.assertEqual(len(line_data_list), 2)  # No discount line

        base_lines = [line_data['base_line'] for line_data in line_data_list]

        tax_group_values = {'name': 'Avatax Brazil', 'company_id': invoice.company_id.id}
        icms = {'name': 'icms', 'l10n_br_avatax_code': 'icms'}
        pis = {'name': 'pis', 'l10n_br_avatax_code': 'pis'}
        base_line_with_tax_values = [
            (base_lines[0], [
                (tax_group_values, icms, {'base_amount_currency': 80.0, 'tax_amount_currency': 8.0}),
                (tax_group_values, pis, {'base_amount_currency': 80.0, 'tax_amount_currency': 1.6}),
            ]),
            (base_lines[1], [
                # Amounts should be correctly distributed even if the taxes have a different order
                (tax_group_values, pis, {'base_amount_currency': 40.0, 'tax_amount_currency': 0.8}),
                (tax_group_values, icms, {'base_amount_currency': 40.0, 'tax_amount_currency': 4.0}),
            ]),
        ]

        result = invoice._process_external_taxes(
            invoice.company_id,
            base_line_with_tax_values,
            'l10n_br_avatax_code',
        )

        self.assertEqual(len(result), 3)  # Discount line should be brought back

        icms_id = str(self.env['account.tax'].search([('l10n_br_avatax_code', '=', 'icms')], limit=1).id)
        pis_id = str(self.env['account.tax'].search([('l10n_br_avatax_code', '=', 'pis')], limit=1).id)

        discount_record = invoice.invoice_line_ids.filtered(lambda l: l.price_unit < 0)
        discount_amounts = result[discount_record]['manual_tax_amounts']
        self.assertAlmostEqual(discount_amounts[icms_id]['tax_amount_currency'], -20 / 80 * 8 - 10 / 40 * 4)
        self.assertAlmostEqual(discount_amounts[pis_id]['tax_amount_currency'], -20 / 80 * 1.6 - 10 / 40 * 0.8)

        # Totals should stay the same: ICMS = 12.0, PIS = 2.4
        total_icms = sum(result[r]['manual_tax_amounts'][icms_id]['tax_amount_currency'] for r in result)
        total_pis = sum(result[r]['manual_tax_amounts'][pis_id]['tax_amount_currency'] for r in result)
        self.assertAlmostEqual(total_icms, 12.0)
        self.assertAlmostEqual(total_pis, 2.4)

    def test_global_discount_redistribution(self):
        """Check if invoice with discount line is redistributed correctly after Avatax call."""
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_invoice_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_invoice_line(product_id=self.product_user_discount, price_unit=-30.0),
            ],
        )

        # Discount is absorbed by other lines: -20 to line 1, -10 to line 2
        # Mock Avatax response with 12% ICMS (tax included) for these lines
        response = {
            'lines': [
                {
                    'lineCode': invoice.invoice_line_ids[0].id,
                    'lineNetFigure': 80.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 9.6,
                        'rate': 12,
                        'subtotalTaxable': 80.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
                {
                    'lineCode': invoice.invoice_line_ids[1].id,
                    'lineNetFigure': 40.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 4.8,
                        'rate': 12,
                        'subtotalTaxable': 40.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
            ],
        }

        # Do it twice to check if it's idempotent
        request_args = []
        for _ in range(2):
            with self._capture_request_br(return_value=response) as mock:
                invoice.button_external_tax_calculation()
                request_args.append(mock.call_args.args[2])

            # Tax totals: 9.6 + 4.8 = 14.4, redistributed to 3 lines
            self.assertRecordValues(invoice, [{
                'amount_untaxed': 120.0,
                'amount_tax': 14.4,
                'amount_total': 134.4,
            }])

            self.assertRecordValues(invoice.invoice_line_ids, [
                {'price_subtotal': 100, 'price_total': 112.0},  # line 100: 100/80 of (base=80, tax=9.6)
                {'price_subtotal': 50, 'price_total': 56.0},  # line 50: 50/40 of (base=40, tax=4.8)
                {'price_subtotal': -30, 'price_total': -33.6},    # discount: -20/80 and -20/40 of both amounts
            ])

        self.assertEqual(request_args[0], request_args[1], "Request to Avalara should be the same on both calls")

    def test_tax_recalculation_after_removing_discount(self):
        """Test that tax calculation works after removing the discount line."""
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(product_id=self.product_user, price_unit=100.0),
                self._prepare_invoice_line(product_id=self.product_user, price_unit=50.0),
                self._prepare_invoice_line(product_id=self.product_user_discount, price_unit=-30.0),
            ],
        )

        # Response for 2 distributed lines
        response_with_discount = {
            'lines': [
                {
                    'lineCode': invoice.invoice_line_ids[0].id,
                    'lineNetFigure': 80.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 9.6,
                        'rate': 12,
                        'subtotalTaxable': 80.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
                {
                    'lineCode': invoice.invoice_line_ids[1].id,
                    'lineNetFigure': 40.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 4.8,
                        'rate': 12,
                        'subtotalTaxable': 40.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
            ],
        }

        with self._capture_request_br(return_value=response_with_discount):
            invoice.button_external_tax_calculation()

        self.assertEqual(invoice.amount_tax, 14.4)

        # Remove the discount line
        invoice.invoice_line_ids.filtered(lambda l: l.price_unit < 0).unlink()

        # Response for 2 lines without discount
        response_without_discount = {
            'lines': [
                {
                    'lineCode': invoice.invoice_line_ids[0].id,
                    'lineNetFigure': 100.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 12.0,
                        'rate': 12,
                        'subtotalTaxable': 100.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
                {
                    'lineCode': invoice.invoice_line_ids[1].id,
                    'lineNetFigure': 50.0,
                    'lineTaxedDiscount': 0,
                    'taxDetails': [{
                        'taxType': 'icms',
                        'tax': 6.0,
                        'rate': 12,
                        'subtotalTaxable': 50.0,
                        'taxImpact': {'impactOnNetAmount': 'Included', 'accounting': 'liability'},
                    }],
                },
            ],
        }

        with self._capture_request_br(return_value=response_without_discount):
            invoice.button_external_tax_calculation()

        self.assertRecordValues(invoice, [{
            'amount_untaxed': 150.0,
            'amount_tax': 18.0,
            'amount_total': 168.0,
        }])

        self.assertRecordValues(invoice.invoice_line_ids, [
            {'price_subtotal': 100.0, 'price_total': 112.0},
            {'price_subtotal': 50.0, 'price_total': 56.0},
        ])

    def test_fail_distribute_negative_amount_lines(self):
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_user,
                    price_unit=50.0,
                ),
                self._prepare_invoice_line(
                    product_id=self.product_user_discount,
                    price_unit=-100.0
                ),
            ],
        )

        with self.assertRaisesRegex(ValidationError, "The document amount must be positive."):
            invoice._get_external_taxes()

    def test_15_credit_note_with_included_tax(self):
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'default_code': 'PROD2',
            'list_price': 800.00,
            'standard_price': 800.00,
            'l10n_br_ncm_code_id': self.env.ref('l10n_br_avatax.02062990').id,
            'l10n_br_source_origin': '0',
            'l10n_br_sped_type': 'FOR PRODUCT',
            'l10n_br_use_type': 'production',
            'supplier_taxes_id': None,
        })

        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner.id,
            'fiscal_position_id': self.fp_avatax.id,
            'invoice_date': '2021-01-01',
            'invoice_line_ids': [
                Command.create({
                    'product_id': product.id,
                    'tax_ids': None,
                    'price_unit': product.list_price,
                }),
            ],
        })

        response = credit_note_generate_response(credit_note.invoice_line_ids)
        with self._capture_request_br(return_value=response):
            credit_note.action_post()

        expected_amounts = {
            'amount_total': 800.0,
            'amount_untaxed': 704.0,
            'amount_tax': 96.0,
        }
        self.assertRecordValues(credit_note, [expected_amounts])
        self.assertEqual(credit_note.tax_totals['total_amount_currency'], expected_amounts['amount_total'])
        self.assertEqual(credit_note.tax_totals['base_amount_currency'], expected_amounts['amount_untaxed'])

    def test_16_nfe_with_order_number_and_item_number(self):
        """ Test that when an order number and item number are provided, they are correctly sent to Avatax. """
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_user,
                    price_unit=100.0,
                    l10n_br_item_number='1234',
                    l10n_br_order_number='5678',
                ),
            ],
        )

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        actual_line = payload['lines'][0]

        self.assertEqual(actual_line['lineAmount'], 100.0)
        self.assertEqual(actual_line['orderNumber'], '5678')
        self.assertEqual(actual_line['orderItemNumber'], '1234')

    def test_17_nfe_with_order_number_and_item_number_none(self):
        """ Test that when an order number and item number are None, they should not be sent to Avatax. """
        invoice = self._create_invoice(
            partner_id=self.partner,
            fiscal_position_id=self.fp_avatax,
            invoice_line_ids=[
                self._prepare_invoice_line(
                    product_id=self.product_user,
                    price_unit=100.0,
                ),
            ],
        )

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        actual_line = payload['lines'][0]

        self.assertTrue('orderNumber' not in actual_line)
        self.assertTrue('orderItemNumber' not in actual_line)

    def test_18_stale_manual_total_excluded_currency(self):
        """Test that manual_total_excluded_currency is updated on recomputation even if it already has a value."""
        invoice, response = self._create_invoice_01_and_expected_response()

        # First call to populate extra_tax_data with correct values.
        with self._capture_request_br(return_value=response):
            invoice.button_external_tax_calculation()

        # Corrupt the manual_total_excluded_currency in extra_tax_data.
        for line in invoice.invoice_line_ids:
            extra_tax_data = line.extra_tax_data
            extra_tax_data['manual_total_excluded_currency'] = 123
            line.write({'extra_tax_data': extra_tax_data})

        # Second call, should correct the stale manual_total_excluded_currency.
        with self._capture_request_br(return_value=response):
            invoice.button_external_tax_calculation()

        # Verify that manual_total_excluded_currency was updated from the fresh Avatax response.
        pre_tax_base = invoice.invoice_line_ids[0].extra_tax_data.get('manual_total_excluded_currency')
        self.assertNotEqual(pre_tax_base, 123)

    def _get_missing_fields_warnings(self, invoice):
        params = invoice._get_l10n_br_avatax_service_params()
        lines = invoice._prepare_l10n_br_avatax_document_lines_service_call(
            params['line_data'], params['use_type'], params['cnae'],
            params['is_service'], params['partner_shipping'], params['company'],
        )
        return invoice._l10n_br_avatax_check_missing_fields_product(lines)

    def test_19_operation_type_product_options_win_over_product(self):
        """Product-option fields resolve from the operation type before the product."""
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.l10n_br_goods_operation_type_id.write({
            'l10n_br_source_origin': '2',
            'l10n_br_sped_type': 'FEEDSTOCK',
            'l10n_br_use_type': 'resale',
        })

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        for line in payload['lines']:
            self.assertEqual(line['useType'], 'resale')
            self.assertEqual(line['itemDescriptor']['source'], '2')
            self.assertEqual(line['itemDescriptor']['productType'], 'FEEDSTOCK')

    def test_20_operation_type_product_options_fallback_to_product(self):
        """When the operation type leaves the product-option fields empty, the product values are used."""
        invoice, _ = self._create_invoice_01_and_expected_response()

        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        for line in payload['lines']:
            self.assertEqual(line['useType'], 'use or consumption')
            self.assertEqual(line['itemDescriptor']['source'], '0')
            self.assertEqual(line['itemDescriptor']['productType'], 'FOR PRODUCT')

    def test_21_line_operation_type_beats_header(self):
        """A line-level operation type override wins over the header operation type."""
        line_op_type = self.env.ref('l10n_br_avatax.operation_type_2')
        line_op_type.write({
            'l10n_br_source_origin': '5',
            'l10n_br_sped_type': 'PACKAGING',
            'l10n_br_use_type': 'production',
        })
        invoice = self._create_invoice_02(operation_types=(line_op_type, False, False, False))
        invoice.l10n_br_goods_operation_type_id.write({
            'l10n_br_source_origin': '2',
            'l10n_br_sped_type': 'FEEDSTOCK',
            'l10n_br_use_type': 'resale',
        })

        lines = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())['lines']
        self.assertEqual(lines[0]['useType'], 'production')
        self.assertEqual(lines[0]['itemDescriptor']['source'], '5')
        self.assertEqual(lines[0]['itemDescriptor']['productType'], 'PACKAGING')
        for line in lines[1:]:
            self.assertEqual(line['useType'], 'resale')
            self.assertEqual(line['itemDescriptor']['source'], '2')
            self.assertEqual(line['itemDescriptor']['productType'], 'FEEDSTOCK')

    def test_22_use_type_priority(self):
        """useType priority: operation type > document-level use type > product."""
        invoice, _ = self._create_invoice_01_and_expected_response()

        # Document-level use type wins over the product value.
        invoice.l10n_br_use_type = 'fixed assets'
        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        for line in payload['lines']:
            self.assertEqual(line['useType'], 'fixed assets')

        # Operation type use type wins over the document-level value.
        invoice.l10n_br_goods_operation_type_id.l10n_br_use_type = 'resale'
        payload = invoice._prepare_l10n_br_avatax_document_service_call(invoice._get_l10n_br_avatax_service_params())
        for line in payload['lines']:
            self.assertEqual(line['useType'], 'resale')

    def test_23_missing_fields_warning_resolved_by_operation_type(self):
        """The missing product-option warning clears when the operation type resolves the value."""
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.invoice_line_ids.product_id.l10n_br_source_origin = False

        warnings = self._get_missing_fields_warnings(invoice)
        self.assertIn('invoice_products_missing_fields_warning', warnings)
        self.assertIn('Source of Origin', warnings['invoice_products_missing_fields_warning']['message'])

        invoice.l10n_br_goods_operation_type_id.l10n_br_source_origin = '2'
        self.assertNotIn('invoice_products_missing_fields_warning', self._get_missing_fields_warnings(invoice))

    def test_24_missing_ncm_warns_regardless_of_operation_type(self):
        """A missing NCM code always warns; the operation type cannot resolve it."""
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.invoice_line_ids.product_id.l10n_br_ncm_code_id = False
        invoice.l10n_br_goods_operation_type_id.write({
            'l10n_br_source_origin': '2',
            'l10n_br_sped_type': 'FEEDSTOCK',
            'l10n_br_use_type': 'resale',
        })

        self.assertIn('products_missing_fields_danger', self._get_missing_fields_warnings(invoice))


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrSettings(TestAvalaraBrInvoiceCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @AccountTestInvoicingCommon.setup_country('br')
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env['res.config.settings'].create({})
        cls.settings.l10n_br_avatax_portal_email = "test@example.com"
        cls.settings.company_id.vat = "00.623.904/0001-73"

    def test_01_create_account_success(self):
        return_value = {
            'avalara_api_id': 'API_ID',
            'avalara_api_key': 'API_KEY',
        }
        with self._capture_request_br(return_value=return_value):
            self.settings.create_account()

        self.assertRecordValues(self.env.company, [{
            'l10n_br_avatax_api_identifier': 'API_ID',
            'l10n_br_avatax_api_key': 'API_KEY',
        }])

    def test_02_create_account_error_type_1(self):
        return_value = {
            'message': 'One or more errors occurred. (CEP \'32516-076\' not found)',
            'isError': True,
        }
        with self._capture_request_br(return_value=return_value), \
             self.assertRaisesRegex(UserError, r'One or more errors occurred. \(CEP \'32516-076\' not found\)'):
            self.settings.create_account()

        return_value = {
            'message': 'An unhandled error occurred. Trace ID: xxx',
            'isError': True
        }
        with self._capture_request_br(return_value=return_value), \
             self.assertRaisesRegex(UserError, 'Please ensure the address on your company is correct'):
            self.settings.create_account()

    def test_03_create_account_error_type_2(self):
        return_value = {
            'message': '{"errors":{"Login do usuário master":["Login já utlizado"]},"title":"One or more validation errors occurred.","status":400,"traceId":"0HMPVCEB27KLU:000000E5"}',
            'isError': True,
        }

        with self._capture_request_br(return_value=return_value), \
             self.assertRaisesRegex(UserError, 'Login já utlizado'):
            self.settings.create_account()

    def test_04_no_false(self):
        """ Do not send "false" to the API for empty fields. It will populate "false" in some of the fields on Avatax's side
        and cause issues during EDI. """
        with self._capture_request_br(return_value={}) as mocked_request:
            self.settings.create_account()

        for k, v in mocked_request.call_args[0][2].items():
            self.assertNotEqual(v, False, f"{k} was False instead of empty string")

    def test_05_formatted_vat(self):
        """ Properly format the VAT numbers to CNPJ even in compact form."""
        with self._capture_request_br(return_value={}) as mocked_request:
            self.settings.create_account()

        arguments = mocked_request.call_args[0][2]
        self.assertEqual(self.settings.company_id.vat, '00623904000173', 'CNPJ should be compacted in internal storage')
        self.assertEqual(arguments['cnpj'], '00.623.904/0001-73', 'CNPJ must be formatted for account creation')

    def test_06_extract_tax_values_multiple_moves(self):
        """Ensure that the tax values are extracted correctly when multiple moves are passed to the function.
        """
        invoice_1, response = self._create_invoice_01_and_expected_response()
        invoice_2, _dummy = self._create_invoice_01_and_expected_response()
        invoices = invoice_1 | invoice_2

        with self._capture_request_br(return_value=response):
            invoices.action_post()
        self.assertTrue(all(invoice.state == 'posted' for invoice in invoices))


@tagged('external_l10n', 'external', '-at_install', 'post_install', '-standard')
class TestAvalaraBrInvoiceIntegration(TestAvalaraBrInvoiceCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_01_invoice_integration_br(self):
        with self._skip_no_credentials():
            invoice, _ = self._create_invoice_01_and_expected_response()
            self.assertInvoice(invoice, test_exact_response=False)
