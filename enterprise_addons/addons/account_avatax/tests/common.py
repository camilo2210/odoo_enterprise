import os
from contextlib import contextmanager
from unittest import SkipTest
from unittest.mock import patch

from odoo.addons.account_avatax.lib.avatax_client import AvataxClient
from odoo.addons.account.tests.common import TestTaxCommon
from odoo.tests import freeze_time
from odoo.tests.common import TransactionCase
from .mocked_invoice_1_response import generate_response as generate_response_invoice_1
from .mocked_invoice_2_response import generate_response as generate_response_invoice_2
from .mocked_invoice_3_response import generate_response as generate_response_invoice_3

NOTHING = object()


class TestAvataxCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.env.company.avalara_api_id = os.getenv("AVALARA_LOGIN_ID") or "AVALARA_LOGIN_ID"
        cls.env.company.avalara_api_key = os.getenv("AVALARA_API_KEY") or "AVALARA_API_KEY"
        cls.env.company.avalara_environment = 'sandbox'
        cls.env.company.avalara_connection_method = 'manual'
        cls.env.company.avalara_commit = True

        # Update address of company
        company = cls.env.user.company_id
        company.write({
            'street': "250 Executive Park Blvd",
            'city': "San Francisco",
            'state_id': cls.env.ref("base.state_us_5").id,
            'country_id': cls.env.ref("base.us").id,
            'zip': "94134",
        })
        company.partner_id.avalara_partner_code = os.getenv("AVALARA_COMPANY_CODE") or "DEFAULT"

        cls.fp_avatax = cls.env['account.fiscal.position'].create({
            'name': 'Avatax',
            'is_avatax': True,
        })

        # Create partner with correct US address
        cls.partner = cls.env["res.partner"].create({
            'name': "Sale Partner",
            'street': "2280 Market St",
            'city': "San Francisco",
            'state_id': cls.env.ref("base.state_us_5").id,
            'country_id': cls.env.ref("base.us").id,
            'zip': "94114",
            'avalara_partner_code': 'CUST123456',
            'property_account_position_id': cls.fp_avatax.id,
        })

        return res

    @classmethod
    @contextmanager
    def _capture_request(cls, return_value=NOTHING, return_func=NOTHING):
        class Capture:
            val = None

            def capture_request(self, *args, **kwargs):
                self.val = kwargs
                if return_value is NOTHING:
                    return return_func(*args, **kwargs)
                return return_value

        capture = Capture()
        with patch(f'{AvataxClient.__module__}.AvataxClient._dispatch', capture.capture_request), patch(f'{AvataxClient.__module__}.AvataxClient.iap_request', capture.capture_request):
            yield capture

    @classmethod
    @contextmanager
    def _skip_no_credentials(cls):
        if not os.getenv("AVALARA_LOGIN_ID") or not os.getenv("AVALARA_API_KEY") or not os.getenv("AVALARA_COMPANY_CODE"):
            raise SkipTest("no Avalara credentials")
        yield


class TestAccountAvataxCommon(TestAvataxCommon, TestTaxCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        res = super().setUpClass()
        cls.foreign_currency = cls.setup_other_currency('EUR')
        cls.product = cls.env["product.product"].create({
            'name': "Product",
            'default_code': 'PROD1',
            'barcode': '123456789',
            'list_price': 15.00,
            'standard_price': 15.00,
            'supplier_taxes_id': None,
            'avatax_category_id': cls.env.ref('account_avatax.DC010000').id,
        })
        cls.product_user = cls.env["product.product"].create({
            'name': "Odoo User",
            'list_price': 35.00,
            'standard_price': 35.00,
            'supplier_taxes_id': None,
            'avatax_category_id': cls.env.ref('account_avatax.DC010000').id,
        })
        cls.product_user_discound = cls.env["product.product"].create({
            'name': "Odoo User Initial Discount",
            'list_price': -5.00,
            'standard_price': -5.00,
            'supplier_taxes_id': None,
            'avatax_category_id': cls.env.ref('account_avatax.DC010000').id,
        })
        cls.product_accounting = cls.env["product.product"].create({
            'name': "Accounting",
            'list_price': 30.00,
            'standard_price': 30.00,
            'supplier_taxes_id': None,
            'avatax_category_id': cls.env.ref('account_avatax.DC010000').id,
        })
        cls.product_expenses = cls.env["product.product"].create({
            'name': "Expenses",
            'list_price': 15.00,
            'standard_price': 15.00,
            'supplier_taxes_id': None,
            'avatax_category_id': cls.env.ref('account_avatax.DC010000').id,
        })
        cls.product_invoicing = cls.env["product.product"].create({
            'name': "Invoicing",
            'list_price': 15.00,
            'standard_price': 15.00,
            'supplier_taxes_id': None,
            'avatax_category_id': cls.env.ref('account_avatax.DC010000').id,
        })

        # This tax is deliberately wrong with an amount of 1. This is used
        # to make sure we use the tax values that Avatax returns and not the tax values
        # Odoo computes (these values would be wrong if a user manually changes it for example).
        cls.example_tax = cls.env["account.tax"].create({
            'name': 'CA STATE 6%',
            'company_id': cls.env.user.company_id.id,
            'amount': 1,
            'amount_type': 'percent',
        })

        return res

    @classmethod
    @freeze_time('2020-01-01')
    def _create_invoice_avatax(cls, **invoice_args):
        invoice_args.setdefault('partner_id', cls.partner)
        invoice_args.setdefault('fiscal_position_id', cls.fp_avatax)
        invoice_args.setdefault('post', True)
        return cls._create_invoice_one_line(
            product_id=cls.product,
            price_unit=100.0,
            **invoice_args,
        )

    @classmethod
    @freeze_time('2021-01-01')
    def _create_invoice_01_and_expected_response(cls):
        invoice = cls._create_invoice(
            partner_id=cls.partner,
            fiscal_position_id=cls.fp_avatax,
            invoice_line_ids=[
                cls._prepare_invoice_line(product_id=cls.product_user),
                cls._prepare_invoice_line(product_id=cls.product_user_discound),
                cls._prepare_invoice_line(product_id=cls.product_accounting),
                cls._prepare_invoice_line(product_id=cls.product_expenses),
                cls._prepare_invoice_line(product_id=cls.product_invoicing),
            ],
        )
        response = generate_response_invoice_1(invoice.invoice_line_ids)
        return invoice, response

    @classmethod
    def _create_invoice_02_and_expected_response(cls):
        invoice = cls._create_invoice(
            partner_id=cls.partner,
            fiscal_position_id=cls.fp_avatax,
            invoice_line_ids=[
                cls._prepare_invoice_line(product_id=cls.product_user, discount=1 / 7 * 100),
                cls._prepare_invoice_line(product_id=cls.product_accounting),
                cls._prepare_invoice_line(product_id=cls.product_expenses),
                cls._prepare_invoice_line(product_id=cls.product_invoicing),
            ],
        )
        response = generate_response_invoice_2(invoice.invoice_line_ids)
        return invoice, response

    @classmethod
    def _create_invoice_03_and_expected_response(cls):
        invoice = cls._create_invoice_one_line(
            product_id=cls.product_accounting,
            partner_id=cls.partner,
            fiscal_position_id=cls.fp_avatax,
        )
        response = generate_response_invoice_3(invoice.invoice_line_ids)
        return invoice, response
