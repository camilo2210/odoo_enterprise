# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json

from odoo import Command
from odoo.addons.l10n_br_avatax.tests.test_br_avatax import TestAvalaraBrCommon
from odoo.tests import tagged


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestAvalaraBrInvoiceFiscalReform(TestAvalaraBrCommon):
    _test_user_groups = None  # FIXME list needed groups

    def test_01_invoice_br_fiscal_reform(self):
        """Set all the new fields for the fiscal reform and verify if the generated request is correct."""
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.company_id.l10n_br_is_icbs = True
        invoice.company_id.partner_id.l10n_br_entity_type = 'business'
        invoice.l10n_br_presence = '2'
        invoice.l10n_br_goods_operation_type_id.l10n_br_customs_regime_id = self.env.ref('l10n_br_edi.customs_regime_capital_goods')

        invoice.invoice_line_ids.product_id.l10n_br_taxable_is = True

        self.product_user.write({
            'l10n_br_nbs_id': self.env.ref('l10n_br_edi.nbs_101'),
            'l10n_br_legal_uom_id': self.env.ref('uom.product_uom_dozen'),
        })

        invoice.partner_id.write({
            'l10n_br_tax_regime': 'simplified',
            'l10n_br_cbs_credit': 5,
            'l10n_br_ibs_credit': 10,
        })

        invoice.invoice_line_ids[0].l10n_br_cbs_ibs_deduction = 7

        # The fiscal reform modules don't change how responses are handled, so use a dummy tax response without any taxes in it.
        with self._with_mocked_l10n_br_iap_request([("calculate_tax", "fiscal_reform_request_goods", "dummy_tax_response")]):
            invoice.button_external_tax_calculation()

        # Test service invoice as well.
        invoice.partner_id.l10n_br_tax_regime = 'individual'
        invoice.partner_id.city_id = self.env['res.city'].create({
            'name': 'test',
            'country_id': self.env.ref('base.br').id
        })
        invoice.invoice_line_ids.mapped('product_id').write({
            'type': 'service',
            'l10n_br_property_service_code_origin_id': self.env['l10n_br.service.code'].create({
                'code': '123',
                'city_id': invoice.partner_id.city_id.id
            }).id
        })
        invoice.l10n_latam_document_type_id = self.env.ref('l10n_br.dt_SE')
        invoice.l10n_br_goods_operation_type_id = self.env.ref('l10n_br_edi.operation_type_sales_other_services_onerous')
        invoice.l10n_br_goods_operation_type_id.l10n_br_service_operation_indicator = '432'

        with self._with_mocked_l10n_br_iap_request([("calculate_tax", "fiscal_reform_request_services", "dummy_tax_response")]):
            invoice.button_external_tax_calculation()

    def test_02_informative_taxes(self):
        invoice, response = self._create_invoice_01_and_expected_response()
        invoice.company_id.l10n_br_is_icbs = True

        # Replace an informative tax with a new fiscal reform one.
        invoice.l10n_br_edi_avatax_data = json.loads(json.dumps(response).replace("aproxtribState", "cbs"))

        rio_city = self.env.ref("l10n_br.city_br_002")
        invoice.invoice_line_ids.mapped("product_id").write(
            {
                "type": "service",
                "l10n_br_property_service_code_origin_id": self.env["l10n_br.service.code"].create(
                    {"code": "12345", "city_id": rio_city.id}
                ),
            }
        )
        invoice.partner_id.city_id = rio_city
        invoice.l10n_latam_document_type_id = self.env.ref("l10n_br.dt_SE")

        payload = invoice._l10n_br_prepare_invoice_payload()

        for line in payload['lines']:
            self.assertTrue(
                any(detail['taxType'] == 'cbs' for detail in line['taxDetails']),
                "CBS tax should remain in the taxDetails, even though it's informative."
            )

        self.assertIn(
            'cbs',
            payload['summary']['taxByType'],
            "CBS tax should remain in the summary, even though it's informative."
        )

        self.assertTrue(
            any(tax['taxType'] == 'cbs' for tax in payload['summary']['taxImpactHighlights']['informative']),
            "CBS tax should remain in the highlights, even though it's informative."
        )

    def test_03_override_cclasstrib(self):
        """
        Test to ensure cClassTrib is overridden inside taxDetails
        when c_class_trib is set on an operation type tax override
        for fiscal reform tax types.
        """

        invoice, response = self._create_invoice_01_and_expected_response()
        invoice.company_id.l10n_br_is_icbs = True

        response_str = json.dumps(response).replace("aproxtribState", "cbs", 1).replace("aproxtribFed", "ibs", 1)
        invoice.l10n_br_edi_avatax_data = json.loads(response_str)

        taxes = {
            code: self.env['account.tax'].create({
                'name': code.upper(),
                'amount_type': 'percent',
                'amount': 10,
                'l10n_br_avatax_code': code,
            })
            for code in ('cbs', 'ibs', 'icms')
        }

        operation_type = self.env['l10n_br.operation.type'].create({
            'name': 'Test cClassTrib Op Type',
            'technical_name': 'test_cclasstrib_op_type',
            'operation_tax_override_ids': [
                Command.create({'tax_id': taxes['cbs'].id, 'c_class_trib': '811001'}),
                Command.create({'tax_id': taxes['ibs'].id, 'c_class_trib': '822002'}),
                Command.create({'tax_id': taxes['icms'].id}),
            ],
        })
        invoice.l10n_br_goods_operation_type_id = operation_type

        payload = invoice._l10n_br_prepare_invoice_payload()

        override_tax_details = {}
        for line in payload['lines']:
            for detail in line.get('taxDetails', []):
                if detail['taxType'] in ('cbs', 'ibs', 'icms'):
                    override_tax_details[detail['taxType']] = detail

        self.assertEqual(override_tax_details.get('cbs', {}).get('cClassTrib'), '811001', "CBS tax must include the configured cClassTrib.")
        self.assertEqual(override_tax_details.get('ibs', {}).get('cClassTrib'), '822002', "IBS tax must include the configured cClassTrib.")
        self.assertNotIn('cClassTrib', override_tax_details.get('icms', {}), "Taxes without a configured c_class_trib must not include cClassTrib.")

    def test_04_taxable_is_cascade(self):
        """notSubjectToIsTax resolves through the operation type before falling back to the product."""
        invoice, _ = self._create_invoice_01_and_expected_response()
        invoice.company_id.l10n_br_is_icbs = True
        op_type = invoice.l10n_br_goods_operation_type_id
        op_type.l10n_br_taxable_is = False
        products = invoice.invoice_line_ids.product_id
        products.l10n_br_taxable_is = True

        def get_lines():
            params = invoice._get_l10n_br_avatax_service_params()
            return invoice._prepare_l10n_br_avatax_document_lines_service_call(
                params['line_data'], params['use_type'], params['cnae'],
                params['is_service'], params['partner_shipping'], params['company'],
            )

        # Operation type unset, product taxable (default) -> not exempt.
        for line in get_lines():
            self.assertFalse(line['goods']['notSubjectToIsTax'])

        # Operation type unset, product not taxable -> exempt.
        products.l10n_br_taxable_is = False
        for line in get_lines():
            self.assertTrue(line['goods']['notSubjectToIsTax'])

        # 'exempt' on the operation type overrides the taxable product.
        op_type.l10n_br_taxable_is = 'exempt'
        products.l10n_br_taxable_is = True
        for line in get_lines():
            self.assertTrue(line['goods']['notSubjectToIsTax'])

        # 'taxable' on the operation type overrides the non-taxable product.
        op_type.l10n_br_taxable_is = 'taxable'
        products.l10n_br_taxable_is = False
        for line in get_lines():
            self.assertFalse(line['goods']['notSubjectToIsTax'])
