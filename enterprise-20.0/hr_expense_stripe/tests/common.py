import base64
import datetime
import json
import logging
from datetime import date
from functools import wraps
from unittest import SkipTest
from unittest.mock import MagicMock, patch

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import Response as HttpResponse
from odoo.tests import Form, freeze_time, tagged
from odoo.tools import BinaryBytes

from odoo.addons.hr_expense.tests.common import TestExpenseCommon
from odoo.addons.hr_expense_stripe.controllers.main import StripeIssuingController
from odoo.addons.hr_expense_stripe.models.hr_expense_stripe_dispute import LOSS_REASONS
from odoo.addons.hr_expense_stripe.utils import format_amount_to_stripe
from odoo.addons.http_routing.tests.common import MockRequest
from odoo.addons.phone_validation.tools import phone_validation

MAKE_STRIPE_REQUEST_PROXY = 'odoo.addons.hr_expense_stripe.{}.make_request_stripe_proxy'


class info_as_debug(logging.Filter):
    """ Demote INFO logs to DEBUG level as a lot of info are logged during webhook receptions, ... """
    def __init__(self, *loggers):
        super().__init__()
        self.loggers_names = loggers

    def filter(self, record):
        if record.levelno == logging.INFO:
            if not logging.getLogger(record.name).isEnabledFor(logging.DEBUG):
                return False

            record.levelno = logging.DEBUG
            record.levelname = 'DEBUG'
        return True

    def __enter__(self):
        for name in self.loggers_names:
            logger = logging.getLogger(name)
            logger.addFilter(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for name in self.loggers_names:
            logger = logging.getLogger(name)
            logger.removeFilter(self)

    def __call__(self, func):
        @wraps(func)
        def deco(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return deco


@freeze_time('2025-06-15')
@tagged('post_install', '-at_install')
class TestExpenseStripeCommon(TestExpenseCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setup_references(cls):
        # TO OVERRIDE
        return '', ''

    @classmethod
    def setUpClass(cls):
        cls.country_code = False
        stripe_country_ref, stripe_currency_ref = cls.setup_references()
        if not stripe_country_ref or not stripe_currency_ref:
            raise SkipTest("Test class not properly configured with country and currency references")

        super().setUpClass()

        cls.stripe_country, cls.stripe_currency = cls.env.ref(stripe_country_ref), cls.env.ref(stripe_currency_ref)
        chart_template_ref = cls.env['account.chart.template']._guess_chart_template(cls.stripe_country)
        template_vals = cls.env['account.chart.template']._get_chart_template_mapping()[chart_template_ref]
        template_module = cls.env['ir.module.module']._get(template_vals['module'])
        if template_module.state != 'installed':
            cls.chart_template = 'generic_coa'  # We want the tests to run without l10n_be installed
        cls.stripe_company_data = cls.setup_other_company(
            name='Stripe Company',
            currency_id=cls.stripe_currency.id,
            country_id=cls.stripe_country.id,
            account_fiscal_country_id=cls.stripe_country.id,
        )
        cls.env = cls.env(context={'allowed_company_ids': cls.stripe_company_data['company'].ids})
        cls.company = cls.stripe_company = cls.stripe_company_data['company']
        cls.stripe_journal = cls.env['account.chart.template'].ref('stripe_issuing_journal')

        if cls.stripe_company.account_fiscal_country_id != cls.stripe_country:
            # If the generic_coa was installed
            cls.stripe_company.write({
                'country_id': cls.stripe_country.id,
                'account_fiscal_country_id': cls.stripe_country.id,
                'stripe_currency_id': cls.stripe_currency.id,
            })
        tax_group = cls.env['account.tax.group'].create({
            'name': "Tax group for Stripe tests",
            'country_id': cls.stripe_country.id,
        })
        cls.stripe_tax = cls.env['account.tax'].create({
            'name': "Tax that is 50%",
            'company_id': cls.stripe_company.id,
            'country_id': cls.stripe_country.id,
            'tax_group_id': tax_group.id,
            'amount': 50,
        })
        cls.stripe_company.account_purchase_tax_id = cls.stripe_tax.copy({'type_tax_use': 'purchase'})
        cls.stripe_company.zip = '1000'
        cls.expense_user_employee.company_ids += cls.env.company
        cls.expense_user_employee.company_id = cls.env.company
        cls.expense_user_employee.partner_id.write({
            'country_id': cls.stripe_country,
            'street': '123 Stripe St',
            'city': 'Brussels',
            'zip': '1000',
        })
        cls.expense_user_manager.company_ids += cls.env.company
        cls.expense_user_manager.company_id = cls.env.company
        cls.stripe_manager_employee = cls.env['hr.employee'].sudo().create({
            'name': 'Stripe Manager Employee',
            'user_id': cls.expense_user_manager.id,
            'company_id': cls.stripe_company.id,
        }).sudo(False)
        cls.stripe_employee = cls.env['hr.employee'].sudo().create({
            'name': 'Stripe Employee',
            'user_id': cls.expense_user_employee.id,
            'company_id': cls.stripe_company.id,
            'birthday': datetime.date(1990, 1, 1),
            'address_id': cls.expense_user_employee.partner_id.id,
            'parent_id': cls.stripe_manager_employee.id,
            'work_phone': '+32000000000',
            'work_email': 'employee@example.com',
        }).sudo(False)
        cls.iap_key_private = cls.env['certificate.key']._generate_ed25519_private_key(company=cls.stripe_company, name="IAP TEST KEY")
        cls.iap_key_public_bytes = cls.iap_key_private._get_public_key_bytes(formatting='base64')
        cls.iap_key_public = cls.env['certificate.key'].create([{
            'name': 'IAP TEST PUBLIC KEY',
            'content': BinaryBytes(base64.b64decode(cls.iap_key_public_bytes)),
            'company_id': cls.stripe_company.id,
        }])
        cls.Controller = StripeIssuingController()

        # Override the signature validation of the controller for the tests
        cls.Controller._validate_signature = MagicMock()
        cls.Controller._validate_signature.return_value = True

        cls.env['ir.config_parameter'].set_str('hr_expense_stripe.stripe_mode', 'test')  # Just to be sure
        # Set taxes belonging to the proper company on the products

        cls.env['product.mcc.stripe.tag'].search([]).product_id.supplier_taxes_id = [
            Command.set(cls.stripe_company.account_purchase_tax_id.ids),
        ]
        cls.env = cls.env(user=cls.expense_user_employee)

    #####################################
    #           Test Actions            #
    #####################################
    def test_create_account(self):
        """ Test the creation of a Stripe account for a company. By mocking the two requests made to Stripe """
        expected_calls = [
            {
                'route': 'accounts',
                'method': 'POST',
                'payload': {
                    'country': self.stripe_country.code,
                    'db_public_key': '__ignored__',
                    'db_uuid': '__ignored__',
                    'db_webhook_url': '__ignored__',
                },
                'return_data': {
                    'id': 'acct_1234567890',
                    'iap_public_key': self.iap_key_public_bytes.decode(),
                    'stripe_pk': 'stripe_public_key',
                },
            },
            {
                'route': 'account_links',
                'method': 'POST',
                'payload': {
                    'account': 'acct_1234567890',
                    'refresh_url': '__ignored__',
                    'return_url': '__ignored__',
                },
                'return_data': {
                    'url': 'WWW.SOME.STRIPE.URL',
                },
            },
        ]
        with self.patch_stripe_requests('models.res_company', expected_calls):
            return_action = self.stripe_company.with_context(skip_stripe_account_creation_commit=True).action_create_stripe_account()
            self.assertDictEqual(return_action, {'type': 'ir.actions.act_url', 'url': 'WWW.SOME.STRIPE.URL', 'target': 'self'})

        self.assertRecordValues(
            self.stripe_company,
            [{
                'stripe_id': 'acct_1234567890',
                'stripe_issuing_activated': True,
                'stripe_account_issuing_status': 'restricted',
                'stripe_account_issuing_tos_accepted': True,
                'stripe_account_issuing_tos_acceptance_date': fields.Date.context_today(self.stripe_company),
            }],
        )
        stripe_public_key = self.env['ir.config_parameter'].sudo().get_str(
            f'hr_expense_stripe.{self.stripe_company.id}_stripe_issuing_pk'
        )
        self.assertEqual('stripe_public_key', stripe_public_key)
        self.assertEqual(self.iap_key_public_bytes, self.stripe_company.stripe_issuing_iap_public_key_id.content.to_base64().encode())

    def test_configure_account(self):
        """" Test the configure account action """
        with self.assertRaises(ValidationError):
            self.stripe_company.action_configure_stripe_account()

        self.setup_account_creation()
        expected_calls = [{
            'route': 'account_links',
            'method': 'POST',
            'payload': {
                'account': 'acct_1234567890',
                'refresh_url': '__ignored__',
                'return_url': '__ignored__',
            },
            'return_data': {
                'url': 'WWW.SOME.STRIPE.URL',
            },
        }]
        # We should always be able to get the link to be redirected to the configuration part after having created the account
        with self.patch_stripe_requests('models.res_company', expected_calls):
            return_action = self.stripe_company.action_configure_stripe_account()
            self.assertDictEqual(return_action, {'type': 'ir.actions.act_url', 'url': 'WWW.SOME.STRIPE.URL', 'target': 'self'})

    def test_refresh_account(self):
        """ Test the refresh account action, and mock an account validation by Stripe """
        self.setup_account_creation()
        self.assertEqual('restricted', self.stripe_company.stripe_account_issuing_status, "Account should be restricted after creation")
        self.stripe_company.env['ir.config_parameter'].sudo().set_str(
            f'hr_expense_stripe.{self.stripe_company.id}_stripe_issuing_pk',
            'OUTDATED PUBLIC KEY',
        )
        expected_calls = [{
            'route': 'accounts/{account}',
            'method': 'GET',
            'payload': {},
            'route_params': {'account': 'acct_1234567890'},
            'return_data': {
                'id': 'acct_1234567890',
                'capabilities': {'card_issuing': 'verified'},
                'stripe_pk': 'NEW PUBLIC KEY',
            },
        }]

        with self.patch_stripe_requests('models.res_company', expected_calls):
            self.stripe_company.action_refresh_stripe_account()
            stripe_pk = self.stripe_company.env['ir.config_parameter'].sudo().get_str(
                f'hr_expense_stripe.{self.stripe_company.id}_stripe_issuing_pk'
            )
            self.assertEqual('NEW PUBLIC KEY', stripe_pk)

    def test_restriction_email_sent_on_status_change(self):
        """ Test that an email is generated when account status drops from verified to restricted. """
        self.setup_account_creation()
        self.stripe_company.stripe_account_issuing_status = 'verified'

        expected_calls = [{
            'route': 'accounts/{account}',
            'method': 'GET',
            'payload': {},
            'route_params': {'account': 'acct_1234567890'},
            'return_data': {
                'id': 'acct_1234567890',
                'capabilities': {'card_issuing': 'inactive'},
                'requirements': {
                    'current_deadline': int(fields.Datetime.now().timestamp()) + 86400
                },
                'stripe_pk': 'NEW PUBLIC KEY',
            },
        }]

        with self.patch_stripe_requests('models.res_company', expected_calls):
            self.stripe_company.action_refresh_stripe_account()

        self.assertEqual(self.stripe_company.stripe_account_issuing_status, 'restricted')

        message = self.env['mail.message'].sudo().search(
            [
                ('subject', '=', 'Action Required: Stripe Issuing Verification'),
                ('model', '=', 'res.company'),
                ('res_id', '=', self.stripe_company.id),
            ],
            limit=1,
        )
        self.assertTrue(message, "An email notifying the restriction should have been sent to the admin.")

    def test_restriction_chatter_fallback(self):
        """ Test that a message is posted to the chatter if the restriction email template is missing. """
        self.setup_account_creation()
        self.stripe_company.stripe_account_issuing_status = 'verified'

        template = self.env.ref('hr_expense_stripe.email_template_hr_expense_stripe_restriction', raise_if_not_found=False)
        if template:
            template.sudo().unlink()

        expected_calls = [{
            'route': 'accounts/{account}',
            'method': 'GET',
            'payload': {},
            'route_params': {'account': 'acct_1234567890'},
            'return_data': {
                'id': 'acct_1234567890',
                'capabilities': {'card_issuing': 'inactive'},
                'requirements': {
                    'current_deadline': int(fields.Datetime.now().timestamp()) + 86400
                },
                'stripe_pk': 'NEW PUBLIC KEY',
            },
        }]

        with self.patch_stripe_requests('models.res_company', expected_calls):
            self.stripe_company.action_refresh_stripe_account()

        message = self.env['mail.message'].sudo().search(
            [
                ('model', '=', 'res.company'),
                ('res_id', '=', self.stripe_company.id),
            ],
            limit=1,
        )
        self.assertTrue(message, "A fallback message should have been posted to the chatter.")
        self.assertIn("Stripe has restricted your account", message.body)

    def test_create_card(self):
        self.setup_account_creation(funds_amount=10000)
        with self.assertRaises(AccessError):
            # The employee user should not be able to create the card
            self.env['hr.expense.stripe.card'].with_user(self.expense_user_employee).create([{
                'employee_id': self.stripe_employee.id,
                'name': 'Test Card',
                'company_id': self.company.id,
            }])
        self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([{
            'employee_id': self.stripe_employee.id,
            'name': 'Test Card',
            'company_id': self.company.id,
        }])

    def test_virtual_card(self):
        self.setup_account_creation(funds_amount=10000)
        card = self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([{
            'employee_id': self.stripe_employee.id,
            'name': 'Test Card',
            'company_id': self.company.id,
            'card_type': 'virtual',
        }])

        expected_calls = [{
            'route': 'cardholders',
            'method': 'POST',
            'payload': '__ignored__',
            'return_data': {
                'id': 'ich_1234567890',
                'livemode': False,
            },
        }]
        with self.patch_stripe_requests('wizard.hr_expense_stripe_cardholder_wizard', expected_calls):
            self.create_cardholder(card, self.stripe_employee)

        expected_calls = [{
            'route': 'cards',
            'method': 'POST',
            'payload': {
                'cardholder': 'ich_1234567890',
                'currency': self.stripe_currency.name,
                'type': 'virtual',
            },
            'return_data': {
                'id': 'ic_1234567890',
                'status': 'active',
                'cancellation_reason': None,
                'last4': '1234',
                'exp_month': 12,
                'exp_year': 2125,
                'livemode': False,
            },
        }]
        with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
            with self.assertRaises(AccessError):
                # The employee user should not be able to activate the card
                card.with_user(self.expense_user_employee).action_activate_card()
            card.with_user(self.expense_user_manager).action_activate_card()
        self.assertRecordValues(card, [
            {'stripe_id': 'ic_1234567890', 'state': 'active', 'last_4': '1234', 'expiration': '12/25'},
        ])

        mail = self.env['mail.mail'].sudo().search(
            [
                ('email_to', '=', self.stripe_employee.work_email),
                ('subject', '=', 'Your Expense Card has been Assigned'),
                ('res_id', '=', card.id),
            ],
            limit=1,
        )
        self.assertTrue(mail, "An email notifying the card assignment should have been sent to the cardholder")

    def test_physical_card_no_shipping(self):
        self.setup_account_creation(funds_amount=10000)
        card = self.create_card(card_type='physical')

        expected_calls = [{
            'route': 'cards',
            'method': 'POST',
            'payload': {
                'cardholder': 'ich_1234567890',
                'currency': self.stripe_currency.name,
                'type': 'physical',
            },
            'return_data': {
                'id': 'ic_1234567890',
                'status': 'inactive',
                'cancellation_reason': None,
                'last4': '1234',
                'exp_month': 12,
                'exp_year': 2125,
                'livemode': False,
                'shipping': {
                    'eta': None,
                    'status': 'pending',
                    'tracking_number': None,
                    'tracking_url': None,
                },
            },
        }]
        with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
            with self.assertRaises(AccessError):
                # The employee user should not be able to activate the card
                card.with_user(self.expense_user_employee).action_activate_card()
            card.with_user(self.expense_user_manager).action_activate_card()

        self.assertRecordValues(card, [
            {'stripe_id': 'ic_1234567890', 'state': 'pending', 'shipping_status': 'pending'},
        ])

        mail = self.env['mail.mail'].sudo().search(
            [
                ('email_to', '=', self.stripe_employee.work_email),
                ('subject', '=', 'Your Expense Card has been Ordered'),
                ('res_id', '=', card.id),
            ],
            limit=1,
        )
        self.assertTrue(mail, "An email notifying the card order should have been sent to the cardholder")

        expected_calls = [{
            'route': 'cardholders/{cardholder_id}',
            'method': 'GET',
            'payload': {},
            'return_data': {
                'id': 'ich_1234567890',
                'livemode': False,
                'phone_number': '+32000000000',
                'billing': {
                    'address': {
                        'country': self.stripe_country.code.lower(),
                    },
                },
            },
        },
        {
            'route': 'cards/{card_id}',
            'method': 'POST',
            'payload': {
                'status': 'active',
            },
            'return_data': {
                'id': 'ic_1234567890',
                'status': 'active',
                'cancellation_reason': None,
                'last4': '1234',
                'exp_month': 12,
                'exp_year': 2125,
                'livemode': False,
                'shipping': {
                    'eta': None,
                    'status': 'pending',
                    'tracking_number': None,
                    'tracking_url': None,
                },
            },
        }]
        with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
            action = card.action_activate_card()
            wizard = self.env['hr.expense.stripe.card.receive.wizard'].with_context(action['context']).create({})

            with self.assertRaises(UserError):
                wizard.action_receive_card()
            wizard.is_confirmed = True

            wizard.last_4_challenge = '1235'
            with self.assertRaises(UserError):
                wizard.action_receive_card()
            wizard.last_4_challenge = card.last_4

            wizard.action_receive_card()

        self.assertRecordValues(card, [{'state': 'active', 'is_delivered': True}])

    def test_create_employee_cardholder(self):
        """ Test that creating a cardholder for an employee without user raises an error """
        self.setup_account_creation(funds_amount=10000)
        new_employee = self.env['hr.employee'].sudo().create([{
            'name': 'Employee Without User',
            'company_id': self.company.id,
        }]).sudo(False)
        with self.assertRaises(ValidationError):
            self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([{
                'employee_id': new_employee.id,
                'name': 'Test Card',
                'company_id': self.company.id,
            }])
        new_employee.sudo().work_email = 'cardholder@employee.com'
        new_employee.sudo().user_id = new_employee._get_or_create_light_user()
        self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([{
            'employee_id': new_employee.id,
            'name': 'Test Card',
            'company_id': self.company.id,
        }])

    def test_create_cardholder(self):
        """ Test the creation of the cardholder wizard """
        self.setup_account_creation(funds_amount=10000)
        card = self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([{
            'employee_id': self.stripe_employee.id,
            'name': 'Test Card',
            'company_id': self.company.id,
        }])
        with self.assertRaises(AccessError):
            # The employee user should not be able to create the cardholder
            card.with_user(self.expense_user_employee).action_open_cardholder_wizard()
        action = card.with_user(self.expense_user_manager).action_open_cardholder_wizard()
        wizard = self.env['hr.expense.stripe.cardholder.wizard'].with_context(action['context']).browse(action['res_id']).sudo()
        with Form(wizard) as form:
            self.assertEqual(form.firstname, 'Stripe')
            self.assertEqual(form.lastname, 'Employee')
            self.assertEqual(form.birthday, '1990-01-01')
            self.assertEqual(form.billing_country_id, self.stripe_country)
            self.assertEqual(form.billing_street, '123 Stripe St')
            self.assertEqual(form.billing_street2, False)
            self.assertEqual(form.billing_city, 'Brussels')
            self.assertEqual(form.billing_zip, '1000')
        expected_calls = [{
            'route': 'cardholders',
            'method': 'POST',  # Even though it's technically a GET request, it generates the new data on Stripe if updated
            'payload': {
                'account': 'acct_1234567890',
                'lang': 'en_US',
                'billing': {'address': {'country': self.stripe_country.code.upper(), 'city': 'Brussels', 'line1': '123 Stripe St', 'postal_code': '1000'}},
                'name': 'Stripe Employee',
                'email': 'expense_user_employee@example.com',
                'individual': {'dob': {'day': 1, 'month': 1, 'year': 1990}, 'first_name': 'Stripe', 'last_name': 'Employee'},
                'preferred_locales': ['en'],
                'phone_number': '+32000000000',
            },
            'return_data': {
                'id': 'ich_1234567890',
                'status': 'active',
                'cancellation_reason': None,
                'last4': '1234',
                'exp_month': 12,
                'exp_year': 2125,
                'livemode': False,
            },
        }]
        with (
            self.patch_stripe_requests('wizard.hr_expense_stripe_cardholder_wizard', expected_calls),
            patch.object(phone_validation, 'phone_format', new=lambda *args, **kwargs: "+32000000000"),
        ):
            wizard.action_save_cardholder()

    def test_dispute_transaction(self):
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        self.env = self.env(user=self.expense_user_manager)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': 'eur',
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': 'BE',
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': 'eur',
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': 'eur',
            },
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'reason': 'webhook_approved',
            }],
            'status': 'pending',
        }

        result = self.simulate_webhook_call(event_data)
        self.assertEqual(result['status'], 200)

        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')])
        with self.assertRaises(UserError, msg="Transaction must be captured to submit a dispute."):
            expense.action_create_dispute()

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_amount,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': 'BE',
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }

        self.simulate_webhook_call(event_data)
        with self.assertRaises(UserError, msg=(
            "You do not have the necessary access rights to file a dispute. "
            "Please contact your expense administrator to file the dispute."
        )):
            expense.with_user(self.expense_user_employee).action_create_dispute()

        dispute_action = expense.action_create_dispute()
        self.assertEqual(dispute_action['type'], 'ir.actions.act_window')

        dispute = self.env['hr.expense.stripe.dispute'].create({
            'currency_id': dispute_action['context']['default_currency_id'],
            'stripe_transaction_id': dispute_action['context']['default_stripe_transaction_id'],
            'card_id': dispute_action['context']['default_card_id'],
            'expense_ids': dispute_action['context']['default_expense_ids'],
            'company_id': dispute_action['context']['default_company_id'],
            'amount': expense.total_amount_currency,
            'reason': 'fraudulent',
            'explanation': 'This is a fraudulent dispute.',
        })

        expected_calls = [{
            'route': 'disputes',
            'method': 'POST',
            'payload': {
                'account': 'acct_1234567890',
                'amount': stripe_amount,
                'evidence[reason]': 'fraudulent',
                'transaction': 'ipi_1234567890',
            },
            'return_data': {
                'amount': stripe_amount,
                'transaction': 'ipi_1234567890',
                'id': 'idp_1234567890',
                'evidence': {
                    'reason': 'fraudulent',
                    'fraudulent': {
                        'explanation': 'This is a fraudulent dispute.',
                    },
                },
                'status': 'unsubmitted',
            },
        }]
        with self.patch_stripe_requests('models.hr_expense_stripe_dispute', expected_calls):
            dispute.action_create_or_update_dispute()

        with self.assertRaises(UserError, msg=(
            "The dispute can only be submitted if the journal entries of all related expenses are posted."
        )):
            dispute.action_submit()

        expense.action_submit()
        self.post_expenses(expense)

        expected_calls = [{
            'route': 'disputes/{dispute_id}/submit',
            'method': 'POST',
            'payload': {
                'account': 'acct_1234567890',
        },
            'route_params': {'dispute_id': dispute.stripe_id},
            'return_data': {
                'amount': stripe_amount,
                'transaction': 'ipi_1234567890',
                'evidence': {
                    'reason': 'fraudulent',
                    'fraudulent': {
                        'explanation': 'This is a fraudulent dispute.',
                    },
                },
                'status': 'submitted',
            },
        }]
        with self.patch_stripe_requests('models.hr_expense_stripe_dispute', expected_calls):
            dispute.action_submit()

        mail = self.env['mail.mail'].sudo().search(
            [
                ('email_to', '=', self.expense_user_manager.email),
                ('subject', 'ilike', 'Your Dispute for the transaction % Has Been Submitted'),
                ('res_id', '=', expense.id),
            ],
            limit=1,
        )
        self.assertTrue(mail, "A notification email should be sent to the manager when the dispute is submitted")

    def test_dispute_transaction_partial_amount(self):
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        self.env = self.env(user=self.expense_user_manager)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        partial_amount = 31.16
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_2234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': 'eur',
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': 'BE',
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': 'eur',
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': 'eur',
            },
            'status': 'pending',
        }
        self.simulate_webhook_call(event_data)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_2234567890',
            'amount': -stripe_amount,
            'authorization': 'iauth_2234567890',
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_amount,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': 'BE',
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)

        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_2234567890')])
        dispute_action = expense.action_create_dispute()
        dispute = self.env['hr.expense.stripe.dispute'].create({
            'currency_id': dispute_action['context']['default_currency_id'],
            'stripe_transaction_id': dispute_action['context']['default_stripe_transaction_id'],
            'card_id': dispute_action['context']['default_card_id'],
            'expense_ids': dispute_action['context']['default_expense_ids'],
            'company_id': dispute_action['context']['default_company_id'],
            'amount': partial_amount,
            'reason': 'fraudulent',
            'explanation': 'This is a partial fraudulent dispute.',
        })

        expected_calls = [{
            'route': 'disputes',
            'method': 'POST',
            'payload': {
                'account': 'acct_1234567890',
                'amount': format_amount_to_stripe(partial_amount, self.stripe_currency),
                'evidence[reason]': 'fraudulent',
                'transaction': 'ipi_2234567890',
            },
            'return_data': {
                'amount': format_amount_to_stripe(partial_amount, self.stripe_currency),
                'transaction': 'ipi_2234567890',
                'id': 'idp_2234567890',
                'evidence': {
                    'reason': 'fraudulent',
                    'fraudulent': {
                        'explanation': 'This is a partial fraudulent dispute.',
                    },
                },
                'status': 'unsubmitted',
            },
        }]
        with self.patch_stripe_requests('models.hr_expense_stripe_dispute', expected_calls):
            dispute.action_create_or_update_dispute()

        self.assertEqual(dispute.amount, partial_amount, "Dispute amount should match the requested partial amount")
        self.assertEqual(expense.disputed_amount, partial_amount, "Expense disputed amount should match the partial amount")

    def test_dispute_transaction_foreign_currency(self):
        """ Test that a dispute is filed in the card currency, not the currency billed by the merchant """
        self.env['res.currency.rate'].sudo().create([{
            'rate': 2,
            'currency_id': self.other_currency.id,
            'name': fields.Date.today(),
        }])
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        self.env = self.env(user=self.expense_user_manager)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        stripe_merchant_amount = format_amount_to_stripe(200, self.other_currency)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': True,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': stripe_merchant_amount,
            'merchant_currency': self.other_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': None,
            'request_history': [{'approved': True, 'amount': stripe_amount, 'reason': 'webhook_approved'}],
            'status': 'pending',
        }
        self.simulate_webhook_call(event_data)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_merchant_amount,
            'merchant_currency': self.other_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)

        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        self.assertRecordValues(expense, [
            {'total_amount': 100.0, 'total_amount_currency': 200.0, 'currency_id': self.other_currency.id},
        ])

        dispute_action = expense.action_create_dispute()
        self.assertEqual(dispute_action['context']['default_currency_id'], self.stripe_currency.id)
        self.assertEqual(expense.disputed_amount, 100.0)

    def test_upload_file(self):
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        self.env = self.env(user=self.expense_user_manager)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': 'eur',
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': 'BE',
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': 'eur',
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': 'eur',
            },
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'reason': 'webhook_approved',
            }],
            'status': 'pending',
        }

        result = self.simulate_webhook_call(event_data)
        self.assertEqual(result['status'], 200)

        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')])
        with self.assertRaises(UserError, msg="Transaction must be captured to submit a dispute."):
            expense.action_create_dispute()

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_amount,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': 'BE',
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }

        self.simulate_webhook_call(event_data)
        with self.assertRaises(UserError, msg=(
            "You do not have the necessary access rights to file a dispute. "
            "Please contact your expense administrator to file the dispute."
        )):
            expense.with_user(self.expense_user_employee).action_create_dispute()

        dispute_action = expense.action_create_dispute()
        self.assertEqual(dispute_action['type'], 'ir.actions.act_window')

        dispute = self.env['hr.expense.stripe.dispute'].create({
            'currency_id': dispute_action['context']['default_currency_id'],
            'stripe_transaction_id': dispute_action['context']['default_stripe_transaction_id'],
            'card_id': dispute_action['context']['default_card_id'],
            'expense_ids': dispute_action['context']['default_expense_ids'],
            'company_id': dispute_action['context']['default_company_id'],
            'amount': expense.total_amount_currency,
            'reason': 'fraudulent',
            'explanation': 'This is a fraudulent dispute.',
        })

        b64_file_data = base64.b64encode(b'hello stripe').decode()
        expected_calls = [{
            'route': 'files',
            'method': 'POST',
            'payload': {
                'account': 'acct_1234567890',
                'purpose': 'dispute_evidence',
            },
            'files': {
                'file': ('evidence.pdf', b'hello stripe', 'application/pdf'),
            },
            'raw': False,
            'return_data': {
                'id': 'file_1234567890',
            },
        }]

        with self.patch_stripe_requests('controllers.main', expected_calls):
            with MockRequest(self.env):
                self.Controller.stripe_issuing_upload_file(
                    model="hr.expense.stripe.dispute",
                    record_id=dispute.id,
                    field_name='additional_documentation',
                    purpose='dispute_evidence',
                    file_name='evidence.pdf',
                    b64_file_data=b64_file_data,
                    content_type='application/pdf',
                )

        self.assertEqual(dispute['additional_documentation'], 'file_1234567890')

    def test_download_file(self):
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        self.env = self.env(user=self.expense_user_manager)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': 'eur',
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': 'BE',
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': 'eur',
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': 'eur',
            },
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'reason': 'webhook_approved',
            }],
            'status': 'pending',
        }

        result = self.simulate_webhook_call(event_data)
        self.assertEqual(result['status'], 200)

        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')])
        with self.assertRaises(UserError, msg="Transaction must be captured to submit a dispute."):
            expense.action_create_dispute()

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_amount,
            'merchant_currency': 'eur',
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': 'BE',
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }

        self.simulate_webhook_call(event_data)
        with self.assertRaises(UserError, msg=(
            "You do not have the necessary access rights to file a dispute. "
            "Please contact your expense administrator to file the dispute."
        )):
            expense.with_user(self.expense_user_employee).action_create_dispute()

        dispute_action = expense.action_create_dispute()
        self.assertEqual(dispute_action['type'], 'ir.actions.act_window')

        dispute = self.env['hr.expense.stripe.dispute'].create({
            'currency_id': dispute_action['context']['default_currency_id'],
            'stripe_transaction_id': dispute_action['context']['default_stripe_transaction_id'],
            'card_id': dispute_action['context']['default_card_id'],
            'expense_ids': dispute_action['context']['default_expense_ids'],
            'company_id': dispute_action['context']['default_company_id'],
            'amount': expense.total_amount_currency,
            'reason': 'fraudulent',
            'explanation': 'This is a fraudulent dispute.',
        })
        dispute['additional_documentation'] = 'file_1234567890'

        file_metadata = {
            'filename': 'evidence.pdf',
        }
        expected_calls = [
            {
                'route': 'files/{file_id}',
                'method': 'GET',
                'payload': {'account': 'acct_1234567890'},
                'route_params': {'file_id': 'file_1234567890'},
                'raw': False,
                'return_data': file_metadata,
            },
            {
                'route': 'files/{file_id}/contents',
                'method': 'GET',
                'payload': {'account': 'acct_1234567890'},
                'route_params': {'file_id': 'file_1234567890'},
                'raw': True,
                'return_data': ('application/pdf', b'%PDF-1.4 test'),
            },
        ]

        with self.patch_stripe_requests('controllers.main', expected_calls):
            with MockRequest(self.env) as request:
                request.make_response.side_effect = lambda data, status=200, headers=None, **kwargs: HttpResponse(
                    data,
                    status=status,
                    headers=headers,
                    **kwargs,
                )
                self.Controller.stripe_issuing_download_file(
                    model='hr.expense.stripe.dispute',
                    record_id=dispute.id,
                    field_name='additional_documentation',
                )
                request.make_response.assert_called_once_with(
                    data=b'%PDF-1.4 test',
                    headers=[
                        ('Content-Type', 'application/pdf'),
                        ('Content-Disposition', 'attachment; filename="evidence.pdf"'),
                    ],
                )

        self.assertFalse(expected_calls, "All expected Stripe proxy calls should have been consumed")

    #####################################
    #           Test Webhooks           #
    #####################################
    def test_webhook_balance_available_event(self):
        """ Test the journal balance update when Stripe receives the money """
        self.setup_account_creation()

        timestamp_before_event = (fields.Datetime.now() + relativedelta(days=-1)).timestamp()
        self.simulate_webhook_call(
            self.get_event_balance_updated_data(format_amount_to_stripe(10.0, self.stripe_currency))
        )
        self.assertEqual(self.stripe_journal.stripe_issuing_balance, 10.0)

        # events may be received out of order, the balance is not updated with an old event
        self.simulate_webhook_call(
            self.get_event_balance_updated_data(format_amount_to_stripe(5.0, self.stripe_currency), timestamp=timestamp_before_event)
        )
        self.assertEqual(self.stripe_journal.stripe_issuing_balance, 10.0)

        # But in order is fine
        timestamp_after_event = (fields.Datetime.now() + relativedelta(seconds=1)).timestamp()  # Tests can go too fast sometimes
        self.simulate_webhook_call(
            self.get_event_balance_updated_data(format_amount_to_stripe(5.0, self.stripe_currency), timestamp=timestamp_after_event)
        )
        self.assertEqual(self.stripe_journal.stripe_issuing_balance, 5.0)

    def test_webhook_issuing_authorization_request_event(self):
        """ Test the `issuing_authorization.request` event. Focusing on the checks the card payments limit"""
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        auth_mcc_product = auth_mcc.product_id
        bad_auth_mcc = self.env['product.mcc.stripe.tag'].search([
            ('code', '!=', '4511'),
            ('product_id', 'not in', [False, auth_mcc_product.id]),
        ], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.request'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': 0,  # Pending
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': self.stripe_currency.name.lower(),
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': self.stripe_currency.name.lower(),
            },
            'status': 'pending',
        }

        # Case 1 No limits
        card.write({
            'spending_policy_country_tag_ids': [Command.clear()],
            'spending_policy_category_tag_ids': [Command.clear()],
            'spending_policy_transaction_amount': 0,
            'spending_policy_interval_amount': 0,
            'spending_policy_interval': 'all_time',
        })
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 2 Bad Country
        card.spending_policy_country_tag_ids = [Command.set(self.env.ref('base.us').ids)]

        result = self.simulate_webhook_call(event_data)
        self.assertFalse(result['content']['approved'], "The authorization should be refused, and an expense created")
        expense = self.env['hr.expense'].search([('stripe_authorization_id', '=', 'iauth_12345678900')])
        self.assertRecordValues(expense, [
            {'total_amount': 100, 'total_amount_currency': 100, 'state': 'refused', 'product_id': auth_mcc_product.id},
        ])
        reason_start = "Your Expense Test Merchant has been refused Reason:"
        self.assertEqual(expense.message_ids[:1].preview, f"{reason_start} Country {self.stripe_country.name} not allowed")

        # Case 3 Good Country
        card.spending_policy_country_tag_ids = [Command.set(self.stripe_country.ids)]
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 4 Bad MCC
        card.write({
            'spending_policy_country_tag_ids': [Command.clear()],
            'spending_policy_category_tag_ids': [Command.set(bad_auth_mcc.ids)],
        })
        event_data['data']['object']['id'] = 'iauth_12345678901'
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].search([('stripe_authorization_id', '=', 'iauth_12345678901')])
        self.assertRecordValues(expense, [
            {'total_amount': 100, 'total_amount_currency': 100, 'state': 'refused', 'product_id': auth_mcc_product.id},
        ])
        self.assertEqual(expense.message_ids[:1].preview, f"{reason_start} MCC code {auth_mcc.code} is not allowed or was not found.")

        # Case 5 Good MCC
        card.spending_policy_category_tag_ids = [Command.set(auth_mcc.ids)]
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 6 Bad Transaction Amount
        card.spending_policy_category_tag_ids = [Command.clear()]
        card.spending_policy_transaction_amount = 50.0
        event_data['data']['object']['id'] = 'iauth_12345678902'
        result = self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].search([('stripe_authorization_id', '=', 'iauth_12345678902')])
        self.assertFalse(result['content']['approved'], "The authorization should be refused, and an expense created")
        self.assertRecordValues(expense, [
            {'total_amount': 100, 'total_amount_currency': 100, 'state': 'refused', 'product_id': auth_mcc_product.id},
        ])
        self.assertEqual(expense.message_ids[:1].preview, f"{reason_start} Transaction amount (100.0) exceeds the maximum allowed")

        # Case 5 Good Transaction Amount
        card.spending_policy_transaction_amount = 150.0
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 6 Bad Interval Amount
        card.spending_policy_transaction_amount = 0
        expenses = self.create_expenses([{
            'product_id': auth_mcc_product.id,
            'total_amount_currency': 10,
            'company_id': self.company.id,
            'currency_id': self.stripe_currency.id,
            'employee_id': self.stripe_employee.id,
            'card_id': card.id,
            'mcc_tag_id': auth_mcc.id,
            'stripe_authorization_id': 'iauth_123456789',
            'stripe_transaction_id': 'ipi_123456789',
            'date': date(2025, 6, 14),
            'name': 'Previous card expense',
        },
        ]).sudo()
        expenses.flush_recordset()  # Needed to be able to get the data
        expenses.action_submit()
        expenses._do_approve()
        self.post_expenses(expenses)
        event_data['data']['object']['id'] = 'iauth_12345678900'
        with freeze_time("2025-06-14 12:00:00"):
            card.spending_policy_interval_amount = 100
            card.spending_policy_interval = 'daily'
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertFalse(result['content']['approved'], "The authorization should be refused")

        with freeze_time("2025-06-15 12:00:00"):  # Next day, daily amount reset
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertTrue(result['content']['approved'], "The authorization should be approved")

            # Weekly interval, 15 is a sunday
            card.spending_policy_interval = 'weekly'
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertFalse(result['content']['approved'], "The authorization should be refused")

        with freeze_time("2025-06-16 12:00:00"):  # Next day (monday), weekly amount reset
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertTrue(result['content']['approved'], "The authorization should be approved")

            # Monthly interval
            card.spending_policy_interval = 'monthly'
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertFalse(result['content']['approved'], "The authorization should be refused")

        with freeze_time("2025-07-01 12:00:00"):
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertTrue(result['content']['approved'], "The authorization should be approved")

            # All time interval
            card.spending_policy_interval = 'all_time'
            event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
            result = self.simulate_webhook_call(event_data)
            self.assertFalse(result['content']['approved'], "The authorization should be refused")

        card.spending_policy_interval_amount = 110
        event_data['data']['object']['created'] = int(fields.Datetime.now().timestamp())
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

    def test_webhook_issuing_authorization_created_event(self):
        """ Test the expense creation when receiving an `issuing_authorization.created` event """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'amount_details': {
                'atm_fee': None,
                'cashback_amount': 0
            },
            'approved': True,
            'card': {'id': card.stripe_id},
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': (self.stripe_country.code or '').upper(),
                'name': 'Test Merchant',
            },
            'pending_request': None,
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'reason': 'webhook_approved'
            }],
            'status': 'pending',
        }
        self.assertFalse(self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')]))
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')])
        self.assertRecordValues(expense, [
            {'total_amount': 100.0, 'total_amount_currency': 100.0, 'state': 'draft', 'product_id': auth_mcc.product_id.id},
        ])

    def test_webhook_issuing_authorization_request_event_range_mcc_case(self):
        """ Test the `issuing_authorization.request` event. Focusing on the checks the card payments limit"""
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '3000-3350')], limit=1)
        card.write({
            'spending_policy_country_tag_ids': [Command.clear()],
            'spending_policy_category_tag_ids': [Command.set(auth_mcc.ids)],
            'spending_policy_transaction_amount': 0,
            'spending_policy_interval_amount': 0,
            'spending_policy_interval': 'all_time',
        })

        # CASE 1: MCC start range
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.request'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': 0,  # Pending
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': '3000',
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': self.stripe_currency.name.lower(),
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': self.stripe_currency.name.lower(),
            },
            'status': 'pending',
        }

        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 2 MCC in range
        event_data['data']['object']['merchant_data']['category_code'] = '3250'
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 2 MCC end range
        event_data['data']['object']['merchant_data']['category_code'] = '3350'
        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should be approved")

        # Case 3 MCC out of ranges
        event_data['data']['object']['merchant_data']['category_code'] = '2000'
        result = self.simulate_webhook_call(event_data)
        self.assertFalse(result['content']['approved'], "The authorization should be refused")
        event_data['data']['object']['merchant_data']['category_code'] = '3400'
        result = self.simulate_webhook_call(event_data)
        self.assertFalse(result['content']['approved'], "The authorization should be refused")

    def test_webhook_issuing_authorization_request_event_unmapped_mcc_case(self):
        """Refused Expenses without a product_id should be created when an unmapped MCC is used."""
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        auth_mcc.sudo().product_id = False

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.request'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': 0,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': self.stripe_currency.name.lower(),
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': self.stripe_currency.name.lower(),
            },
            'status': 'pending',
        }

        result = self.simulate_webhook_call(event_data)
        self.assertFalse(result['content']['approved'], "The authorization should be refused")

        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_12345678900')])
        self.assertRecordValues(expense, [
            {'state': 'refused', 'product_id': False},
        ])

    def test_webhook_issuing_authorization_updated_event(self):
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.updated'  # Works the same way as created
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'amount_details': {
                'atm_fee': None,
                'cashback_amount': 0
            },
            'approved': False,
            'card': {'id': card.stripe_id},
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': (self.stripe_country.code or '').upper(),
                'name': 'Test Merchant',
            },
            'pending_request': None,
            'request_history': [{
                'approved': False,
                'amount': stripe_amount,
                'reason': 'webhook_timeout'
            }],
            'status': 'closed',
        }
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')])
        self.assertRecordValues(expense, [
            {'total_amount': 100.0, 'total_amount_currency': 100.0, 'state': 'refused', 'product_id': auth_mcc.product_id.id},
        ])

    def test_webhook_issuing_authorization_request_no_date(self):
        """ Test the `issuing_authorization.request` event. Focusing on corner cases where expenses without a date may generate a traceback
        """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        card.write({
            'spending_policy_country_tag_ids': [Command.clear()],
            'spending_policy_category_tag_ids': [Command.clear()],
            'spending_policy_transaction_amount': 0,
            'spending_policy_interval_amount': 10000,
            'spending_policy_interval': 'daily',
        })
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        auth_mcc_product = auth_mcc.product_id

        # An expense created with the card has no date
        self.create_expenses([{
            'product_id': auth_mcc_product.id,
            'total_amount_currency': 10,
            'company_id': self.company.id,
            'currency_id': self.stripe_currency.id,
            'employee_id': self.stripe_employee.id,
            'card_id': card.id,
            'mcc_tag_id': auth_mcc.id,
            'stripe_authorization_id': 'iauth_12345678900',
            'stripe_transaction_id': 'ipi_12345678900',
            'date': False,
            'name': 'Previous card expense',
        }])

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.request'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': 0,  # Pending
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': 0,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': {
                'amount': stripe_amount,
                'currency': self.stripe_currency.name.lower(),
                'is_amount_controllable': False,
                'merchant_amount': stripe_amount,
                'merchant_currency': self.stripe_currency.name.lower(),
            },
            'status': 'pending',
        }

        result = self.simulate_webhook_call(event_data)
        self.assertTrue(result['content']['approved'], "The authorization should not fail due to the lack of date")

    def test_webhook_issuing_authorization_updated_event_amount_zero(self):
        """ An authorization updated with an amount of 0 acts as a reversal of the authorization,
        which can happen after a certain amount of time if the authorization is not captured or if the vendor cancels it on their side
        """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        auth_mcc_product = auth_mcc.product_id

        # STEP 1: Create the authorization with a pending amount, which should create the expense in draft with the pending amount
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': None,
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'reason': 'webhook_approved',
            }],
            'status': 'pending',
        }

        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_12345678900')])
        self.assertRecordValues(expense, [
            {'total_amount': 100.0, 'total_amount_currency': 100.0, 'state': 'draft', 'product_id': auth_mcc_product.id},
        ])

        # STEP 2: Update the authorization with an amount of 0, which should reverse the authorization and set the expense to refused
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.updated'  # Works the same way as created
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': 0,
            'amount_details': {
                'atm_fee': None,
                'cashback_amount': 0
            },
            'approved': True,
            'card': {'id': card.stripe_id},
            'merchant_amount': 0,  # Amount is set to 0 to indicate a reversal
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': (self.stripe_country.code or '').upper(),
                'name': 'Test Merchant',
            },
            'pending_request': None,
            'request_history': [{
                "amount": stripe_amount,
                "amount_details": {
                    "atm_fee": None,
                    "cashback_amount": None,
                },
                "approved": True,
                "currency": self.stripe_currency.name.lower(),
                "merchant_amount": stripe_amount,
                "merchant_currency": self.stripe_currency.name.lower(),
                "reason": "webhook_approved",
                "reason_message": None,
            }],
            'status': 'reversed',
        }
        self.simulate_webhook_call(event_data)
        self.assertRecordValues(expense, [
            {'total_amount': 100.0, 'total_amount_currency': 100.0, 'state': 'refused', 'product_id': auth_mcc.product_id.id},
        ])

    def test_webhook_issuing_authorization_foreign_currency_updated_flow(self):
        """ Test the consistency of the currency when an authorization is updated along the way """

        self.assertTrue(self.other_currency - self.stripe_currency, "The other_currency should be different from the stripe_currency")
        self.env['res.currency.rate'].sudo().create([{
            'rate': 2,
            'currency_id': self.other_currency.id,
            'name': fields.Date.today(),
        }])
        stripe_rate = 125

        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        stripe_amount = format_amount_to_stripe(100, self.stripe_currency)

        # Use a different rate than the database rate
        stripe_merchant_amount = format_amount_to_stripe(100 * stripe_rate, self.other_currency)

        # STEP 1: Create the authorization with a pending amount in foreign currency
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': stripe_merchant_amount,
            'merchant_currency': self.other_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': None,
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'currency': self.stripe_currency.name.lower(),
                'merchant_amount': stripe_merchant_amount,
                'merchant_currency': self.other_currency.name.lower(),
                'reason': 'webhook_approved',
            }],
            'status': 'pending',
        }
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].search([('stripe_authorization_id', '=', 'iauth_12345678900')])
        self.assertRecordValues(expense, [
            {'total_amount': 100.0, 'total_amount_currency': 12500.0, 'currency_id': self.other_currency.id, 'state': 'draft'},
        ])

        # STEP 2: Update the authorization with a pending amount in foreign currency
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.updated'
        event_data['data']['object'] = {
            'id': 'iauth_12345678900',
            'object': 'issuing.authorization',
            'amount': format_amount_to_stripe(90, self.stripe_currency),
            'approved': False,
            'authorization_method': 'online',
            'card': {'id': card.stripe_id},
            'cardholder': 'ic_1234567890',
            'currency': self.stripe_currency.name.lower(),
            'livemode': False,
            'merchant_amount': format_amount_to_stripe(90 * stripe_rate, self.other_currency),
            'merchant_currency': self.other_currency.name.lower(),
            'merchant_data': {
                'category': auth_mcc.stripe_name,
                'category_code': auth_mcc.code,
                'country': self.stripe_country.code.lower(),
                'name': 'Test Merchant',
                'tax_id': None,
            },
            'pending_request': None,
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'currency': self.stripe_currency.name.lower(),
                'merchant_amount': stripe_merchant_amount,
                'merchant_currency': self.other_currency.name.lower(),
                'reason': 'webhook_approved',
            }],
            'status': 'pending',
        }
        self.simulate_webhook_call(event_data)
        self.assertRecordValues(expense, [
            {'total_amount': 90.0, 'total_amount_currency': 11250.0, 'currency_id': self.other_currency.id, 'state': 'draft'},
        ])

        # STEP 3: Close the authorization with a pending amount in foreign currency
        event_data['data']['object']['status'] = 'closed'
        self.simulate_webhook_call(event_data)
        self.assertRecordValues(expense, [
            {'total_amount': 90.0, 'total_amount_currency': 11250.0, 'currency_id': self.other_currency.id, 'state': 'draft'},
        ])

    def test_webhook_issuing_card_updated_event(self):
        """ Test the card updates when receiving an `issuing_card.updated` event (mostly for card-stop) cancellations """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_card.updated'  # Works the same way as created
        event_data['data']['object'] = {
            'id': 'ic_1234567890',
            'cancellation_reason': None,
            'shipping': None,
            'status': 'inactive',
            'type': 'virtual',
        }
        self.assertRecordValues(card, [
            {'stripe_id': 'ic_1234567890', 'state': 'active'},
        ])
        self.simulate_webhook_call(event_data)
        self.assertRecordValues(card, [
            {'stripe_id': 'ic_1234567890', 'state': 'inactive'},
        ])
        event_data['data']['object'] = {
            'id': 'ic_1234567890',
            'cancellation_reason': 'none',
            'shipping': None,
            'status': 'canceled',
            'type': 'virtual',
        }
        self.simulate_webhook_call(event_data)
        self.assertRecordValues(card, [
            {'stripe_id': 'ic_1234567890', 'state': 'canceled'},
        ])

    def test_webhook_issuing_transaction_created_event(self):
        """ Test the bank statement line and expense are created
        when an `issuing_transaction.created` event is received.
        Also test that two transactions for the same authorization generates a split expense
        """
        self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        stripe_amount = format_amount_to_stripe(-500, self.stripe_currency)
        today = date(2025, 6, 15)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': 'ic_1234567890',
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567890'),
        ])
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        self.assertRecordValues(bank_statement_line, [
            {'amount': -500.0, 'date': today, 'payment_ref': 'Card ending in 1234 payment to Test Merchant', 'state': 'posted'},
        ])
        self.assertRecordValues(expense, [
            {'total_amount': 500.0, 'total_amount_currency': 500.0, 'state': 'draft', 'product_id': auth_mcc.product_id.id},
        ])

        # Test several captures for the same authorization create split expenses
        event_data['data']['object']['id'] = 'ipi_1234567891'
        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567891'),
        ])
        self.assertEqual(len(bank_statement_line), 1, "A bank statement line should have have been created for the transaction")
        expense_two = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567891')])
        self.assertRecordValues(expense_two, [
            {'total_amount': 500.0, 'total_amount_currency': 500.0, 'split_expense_origin_id': expense.id},
        ])
        expenses = expense + expense_two
        expenses.action_submit()
        expenses._do_approve()
        self.post_expenses(expenses)
        self.assertRecordValues(expenses, [
            {'state': 'paid'},
            {'state': 'paid'},
        ])

        # Test refunds
        event_data['data']['object'].update({
            'id': 'ipi_1234567893',
            'amount': format_amount_to_stripe(300, self.stripe_currency),
            'type': 'refund',
        })
        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567893'),
        ])
        self.assertRecordValues(bank_statement_line, [
            {'amount': 300.0, 'date': today, 'payment_ref': 'Card ending in 1234 payment to Test Merchant', 'state': 'posted'},
        ])

    def test_webhook_issuing_transaction_created_event_reconciliation(self):
        """ Test that an `issuing_transaction.created` event creates a transaction that is reconciled with the right expense move
        """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        auth_mcc.product_id.sudo().supplier_taxes_id = [Command.set(self.stripe_company.account_purchase_tax_id.ids)]
        stripe_amount = format_amount_to_stripe(-500, self.stripe_currency)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_authorization.created'
        event_data['data']['object'] = {
            'id': 'iauth_1234567890',
            'object': 'issuing.authorization',
            'amount': stripe_amount,
            'amount_details': {
                'atm_fee': None,
                'cashback_amount': 0
            },
            'approved': True,
            'card': {'id': card.stripe_id},
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': auth_mcc.code,
                'country': (self.stripe_country.code or '').upper(),
                'name': 'Test Merchant',
            },
            'pending_request': None,
            'request_history': [{
                'approved': True,
                'amount': stripe_amount,
                'reason': 'webhook_approved'
            }],
            'status': 'pending',
        }

        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_authorization_id', '=', 'iauth_1234567890')])
        with self.assertRaises(UserError, msg="Cannot submit a reserved expesnse"):
            expense.action_submit()

        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567890'),
        ])
        self.assertFalse(bank_statement_line)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': 'ic_1234567890',
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)

        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567890'),
        ])
        self.assertRecordValues(bank_statement_line, [
            {'amount': -500.0, 'payment_ref': 'Card ending in 1234 payment to Test Merchant', 'state': 'posted', 'amount_residual': 500.0},
        ])

        expense.action_submit()
        expense._do_approve()
        self.post_expenses(expense)
        self.assertRecordValues(expense, [
            {'total_amount': 500.0, 'total_amount_currency': 500.0, 'state': 'paid', 'product_id': auth_mcc.product_id.id},
        ])
        self.assertRecordValues(bank_statement_line, [
            {'amount': -500.0, 'payment_ref': 'Card ending in 1234 payment to Test Merchant', 'state': 'posted', 'amount_residual': 0.0},
        ])

    def test_webhook_issuing_transaction_updated_event(self):
        """ Test the `issuing_transaction.updated` event refund is properly reflected in the bank statement line and expense """
        self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        auth_mcc = self.env['product.mcc.stripe.tag'].search([('code', '=', '4511')], limit=1)
        stripe_amount = format_amount_to_stripe(-500, self.stripe_currency)
        today = date(2025, 6, 15)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': stripe_amount,
            'authorization': 'iauth_1234567890',
            'card': 'ic_1234567890',
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567890'),
        ])
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        self.assertRecordValues(bank_statement_line, [
            {'amount': -500.0, 'date': today, 'payment_ref': 'Card ending in 1234 payment to Test Merchant', 'state': 'posted'},
        ])
        self.assertRecordValues(expense, [
            {'total_amount': 500.0, 'total_amount_currency': 500.0, 'state': 'draft', 'product_id': auth_mcc.product_id.id},
        ])

        # Now update the transaction (e.g., partial refund)
        event_data['type'] = 'issuing_transaction.updated'
        event_data['data']['object']['amount'] = format_amount_to_stripe(-300, self.stripe_currency)
        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'ipi_1234567890'),
        ])
        self.assertRecordValues(bank_statement_line, [
            {'amount': -300.0, 'date': today, 'payment_ref': 'Card ending in 1234 payment to Test Merchant', 'state': 'posted'},
        ])
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        self.assertRecordValues(expense, [
            {'total_amount': 300.0, 'total_amount_currency': 300.0, 'state': 'draft', 'product_id': auth_mcc.product_id.id},
        ])

    def test_webhook_topup_succeeded_event(self):
        """ Test that a bank statement line is created when a top-up is succeeded """
        self.setup_account_creation()
        topup_amount = 50.0
        stripe_topup_amount = format_amount_to_stripe(topup_amount, self.stripe_currency)
        event_data = self.get_event_expected_data()
        event_data['type'] = 'topup.succeeded'
        event_data['data']['object'] = {
            'id': 'tu_1234567890',
            'object': 'topup',
            'amount': stripe_topup_amount,
            'currency': self.stripe_currency.name.lower(),
            'description': 'Test Top-Up',
            'status': 'succeeded',
            'created': int(fields.Datetime.now().timestamp()),
        }

        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'tu_1234567890'),
        ])
        self.assertEqual(len(bank_statement_line), 1, "A bank statement line should have been created for the top-up")
        self.assertEqual(bank_statement_line.amount, topup_amount, "The bank statement line should have the correct amount")

        # if we receive the data again, no duplicate should be created
        self.simulate_webhook_call(event_data)
        bank_statement_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', 'tu_1234567890'),
        ])
        self.assertEqual(len(bank_statement_line), 1, "A bank statement line should have been created for the top-up")

    def test_physical_card_shipping(self):
        self.setup_account_creation(funds_amount=10000)
        for i, final_state in enumerate(['delivered', 'returned', 'failure', 'canceled']):
            with self.subTest(card_shipping_final_state=final_state):
                card = self.create_card(card_type='physical', create_cardholder=final_state == 'delivered')

                stripe_id = 'ic_' + str(1234567890 + i)
                eta = int((fields.Datetime.now() + relativedelta(days=7)).timestamp())
                expected_calls = [{
                    'route': 'cards',
                    'method': 'POST',
                    'payload': {
                        'cardholder': card.employee_id.sudo().private_stripe_id,
                        'currency': self.stripe_currency.name,
                        'type': 'physical',
                    },
                    'return_data': {
                        'id': stripe_id,
                        'status': 'inactive',
                        'cancellation_reason': None,
                        'last4': '1234',
                        'exp_month': 12,
                        'exp_year': 2125,
                        'livemode': False,
                        'shipping': {
                            'eta': eta,
                            'status': 'pending',
                            'tracking_number': None,
                            'tracking_url': None,
                        },
                    },
                }]
                with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
                    card.with_user(self.expense_user_manager).action_activate_card()

                self.assertRecordValues(card, [
                    {'state': 'pending', 'shipping_status': 'pending', 'ordered_by': self.expense_user_manager.id},
                ])
                mail = self.env['mail.mail'].sudo().search(
                    [
                        ('email_to', '=', self.stripe_employee.work_email),
                        ('subject', '=', 'Your Expense Card has been Ordered'),
                        ('res_id', '=', card.id),
                    ],
                    limit=1,
                )
                self.assertTrue(mail, "An email notifying the card order should have been sent to the cardholder")

                # Little particularity of Stripe, if the card doesn't use a custom desig the card will skip the state
                # submitted and go directly to shipped. However, the previous_shipping_status is still submitted.
                self.simulate_card_shipping(card, status='shipped', tracking_number='TRACK123', tracking_url='http://tracking.url/TRACK123', previous_shipping_status='submitted')
                self.assertRecordValues(card, [{'state': 'pending', 'shipping_status': 'shipped'}])

                mail = self.env['mail.mail'].sudo().search(
                    [
                        ('email_to', '=', card.ordered_by.email_formatted),
                        ('subject', '=', 'Your Expense Card Has Been Shipped'),
                        ('res_id', '=', card.id),
                    ],
                    limit=1,
                )
                self.assertTrue(mail, "An email notifying the card shipment should have been sent to the cardholder")

                if final_state == 'delivered':
                    self.simulate_card_shipping(card, status=final_state)
                    self.assertRecordValues(card, [{'state': 'pending', 'shipping_status': 'delivered'}])
                else:
                    expected_calls = [{
                        'route': 'cards/{card_id}',
                        'method': 'POST',
                        'payload': {
                            'status': 'canceled',
                        },
                        'return_data': {
                            'id': stripe_id,
                            'status': 'canceled',
                            'cancellation_reason': 'none',
                            'last4': '1234',
                            'exp_month': 12,
                            'exp_year': 2125,
                            'livemode': False,
                            'shipping': {
                                'eta': eta,
                                'status': final_state,
                                'tracking_number': card.tracking_number,
                                'tracking_url': card.tracking_url,
                            },
                        },
                    }]
                    with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
                        self.simulate_card_shipping(card, status=final_state)
                        self.assertRecordValues(card, [{'state': 'canceled', 'shipping_status': final_state}])

                    mail = self.env['mail.mail'].sudo().search(
                        [
                            ('email_to', '=', card.ordered_by.email_formatted),
                            ('subject', '=', 'Your Expense Card Has Been Canceled'),
                            ('res_id', '=', card.id),
                        ],
                        limit=1,
                    )
                    self.assertTrue(mail, "An email notifying the card cancellation should have been sent to the cardholder")

    def test_stripe_expense_card_without_spending_policy_interval(self):
        """
        Ensure that when no spending policy interval is set, it defaults to
        'all_time' and does not trigger the Stripe limit warning.
        """
        card_form = Form(self.env['hr.expense.stripe.card'].sudo())
        self.assertEqual(card_form.spending_policy_interval, 'all_time')
        self.assertFalse(card_form.has_limit_higher_than_stripe_warning)

        card_form.spending_policy_interval = False
        self.assertFalse(card_form.has_limit_higher_than_stripe_warning)

    def test_webhook_auto_dispute_negative_balance(self):
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)

        transaction_id = 'ipi_1234567890'
        amount = 100.0
        stripe_amount = format_amount_to_stripe(-amount, self.stripe_currency)
        stripe_dispute_amount = format_amount_to_stripe(amount, self.stripe_currency)

        # Create a force-capture transaction (no authorization) so it is eligible for auto-dispute.
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': transaction_id,
            'amount': stripe_amount,
            'authorization': False,
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)

        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', transaction_id)])
        self.assertEqual(len(expense), 1, "An expense should have been created from the force-capture transaction")

        # Ensure the expense has a posted move so dispute funds movements can generate reversal entries.
        expense.action_submit()
        expense._do_approve()
        self.post_expenses(expense)
        self.assertEqual(expense.state, 'paid', "Expense should be paid before funds reinstated/rescinded events")

        expected_calls = [
            {
                'route': 'disputes',
                'method': 'POST',
                'payload': {
                    'account': 'acct_1234567890',
                    'amount': stripe_dispute_amount,
                    'evidence[reason]': 'no_valid_authorization',
                    'transaction': transaction_id,
                },
                'return_data': {
                    'id': 'idp_1234567890',
                    'amount': stripe_dispute_amount,
                    'transaction': transaction_id,
                    'status': 'unsubmitted',
                    'evidence': {
                        'reason': 'no_valid_authorization',
                        'no_valid_authorization': {},
                    },
                },
            },
            {
                'route': 'disputes/{dispute_id}/submit',
                'method': 'POST',
                'payload': {'account': 'acct_1234567890'},
                'return_data': {
                    'id': 'idp_1234567890',
                    'amount': stripe_dispute_amount,
                    'transaction': transaction_id,
                    'status': 'submitted',
                    'evidence': {
                        'reason': 'no_valid_authorization',
                        'no_valid_authorization': {},
                    },
                },
            },
        ]

        # Trigger negative balance to auto-create and auto-submit dispute(s) for force-captures.
        timestamp_after_event = (fields.Datetime.now() + relativedelta(seconds=1)).timestamp()
        event_data = self.get_event_balance_updated_data(
            format_amount_to_stripe(-amount, self.stripe_currency),
            timestamp=timestamp_after_event,
        )
        with self.patch_stripe_requests('models.hr_expense_stripe_dispute', expected_calls):
            self.simulate_webhook_call(event_data)

        dispute = expense.dispute_id
        self.assertTrue(dispute, "A dispute should have been created automatically")
        self.assertRecordValues(dispute, [{
            'stripe_id': dispute.stripe_id,
            'reason': 'no_valid_authorization',
            'state': 'submitted',
        }])

        reinstated_event_data = self.get_event_expected_data()
        reinstated_event_data['type'] = 'issuing_dispute.funds_reinstated'
        reinstated_event_data['data']['object'] = {
            'id': dispute.stripe_id,
            'transaction': transaction_id,
            'amount': stripe_dispute_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [{'net': stripe_dispute_amount}]},
        }]):
            self.simulate_webhook_call(reinstated_event_data)
        reinstated_stmt_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', dispute.stripe_id),
            ('payment_ref', '=', 'Dispute funds reinstated'),
        ])
        self.assertRecordValues(reinstated_stmt_line, [{
            'amount': amount,
            'payment_ref': 'Dispute funds reinstated',
            'state': 'posted',
        }])

        rescinded_event_data = self.get_event_expected_data()
        rescinded_event_data['type'] = 'issuing_dispute.funds_rescinded'
        rescinded_event_data['data']['object'] = {
            'id': dispute.stripe_id,
            'transaction': transaction_id,
            'amount': stripe_dispute_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [{'net': stripe_dispute_amount}, {'net': -stripe_dispute_amount}]},
        }]):
            self.simulate_webhook_call(rescinded_event_data)
        rescinded_stmt_line = self.env['account.bank.statement.line'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('stripe_id', '=', dispute.stripe_id),
            ('payment_ref', '=', 'Dispute funds rescinded'),
        ])
        self.assertRecordValues(rescinded_stmt_line, [{
            'amount': -amount,
            'payment_ref': 'Dispute funds rescinded',
            'state': 'posted',
        }])

    def test_webhook_auto_dispute_negative_balance_foreign_currency(self):
        """ Test that a force capture billed in a foreign currency is disputed for the settled amount """
        self.env['res.currency.rate'].sudo().create([{
            'rate': 2,
            'currency_id': self.other_currency.id,
            'name': fields.Date.today(),
        }])
        # The account is left unfunded: the force capture is what drives the issuing balance negative
        card = self.setup_account_creation(create_active_card_for=self.stripe_employee)
        amount = 100.0
        stripe_amount = format_amount_to_stripe(amount, self.stripe_currency)
        transaction_id = 'ipi_1234567890'

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': transaction_id,
            'amount': -stripe_amount,
            'authorization': False,  # Force captures don't have any authorization
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': format_amount_to_stripe(-200, self.other_currency),
            'merchant_currency': self.other_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)

        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', transaction_id)])
        self.assertRecordValues(expense, [
            {'total_amount': amount, 'total_amount_currency': 200.0, 'currency_id': self.other_currency.id, 'state': 'draft'},
        ])

        expected_calls = [
            {
                'route': 'disputes',
                'method': 'POST',
                'payload': {
                    'account': 'acct_1234567890',
                    'amount': stripe_amount,  # The settled amount, not the 200 billed by the merchant
                    'evidence[reason]': 'no_valid_authorization',
                    'transaction': transaction_id,
                },
                'return_data': self.get_stripe_dispute_data(transaction_id, stripe_amount, 'unsubmitted', reason='no_valid_authorization'),
            },
            {
                'route': 'disputes/{dispute_id}/submit',
                'method': 'POST',
                'payload': {'account': 'acct_1234567890'},
                'return_data': self.get_stripe_dispute_data(transaction_id, stripe_amount, 'submitted', reason='no_valid_authorization'),
            },
        ]
        event_data = self.get_event_balance_updated_data(
            -stripe_amount,
            timestamp=(fields.Datetime.now() + relativedelta(seconds=1)).timestamp(),
        )
        with self.patch_stripe_requests('models.hr_expense_stripe_dispute', expected_calls):
            self.simulate_webhook_call(event_data)

        self.assertRecordValues(expense.dispute_id, [
            {'currency_id': self.stripe_currency.id, 'amount': amount, 'state': 'submitted'},
        ])
        self.assertEqual(expense.disputed_amount, amount)

    def test_webhook_issuing_dispute_created_event(self):
        """ Test that a dispute filed outside of Odoo is created on reception of the event """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        amount = 100.0
        stripe_amount = format_amount_to_stripe(amount, self.stripe_currency)
        transaction_id = 'ipi_1234567890'

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': transaction_id,
            'amount': -stripe_amount,
            'authorization': False,
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', transaction_id)])

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_dispute.created'
        event_data['data']['object'] = self.get_stripe_dispute_data(
            transaction_id, stripe_amount, 'unsubmitted', explanation='Fraudulent transaction.',
        )
        self.simulate_webhook_call(event_data)

        self.assertRecordValues(expense.dispute_id, [{
            'stripe_id': 'idp_1234567890',
            'card_id': card.id,
            'currency_id': self.stripe_currency.id,
            'amount': amount,
            'reason': 'fraudulent',
            'explanation': 'Fraudulent transaction.',
            'state': 'unsubmitted',
        }])

    def test_webhook_issuing_dispute_closed_event(self):
        """ Test that closing a submitted dispute records its outcome and notifies its submitter once """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)
        amount = 100.0
        stripe_amount = format_amount_to_stripe(amount, self.stripe_currency)
        transaction_id = 'ipi_1234567890'

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': transaction_id,
            'amount': -stripe_amount,
            'authorization': False,
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', transaction_id)])
        # The submission itself is covered by `test_dispute_transaction`
        dispute = self.env['hr.expense.stripe.dispute'].sudo().create({
            'stripe_id': 'idp_1234567890',
            'stripe_transaction_id': transaction_id,
            'card_id': card.id,
            'currency_id': self.stripe_currency.id,
            'company_id': self.stripe_company.id,
            'expense_ids': [Command.set(expense.ids)],
            'amount': amount,
            'reason': 'fraudulent',
            'explanation': 'Fraudulent transaction.',
            'state': 'submitted',
            'submitted_by': self.expense_user_manager.id,
        })

        # The amended evidence is outside of {'loss_reason', 'state'}: only the webhook may write it
        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_dispute.closed'
        event_data['data']['object'] = self.get_stripe_dispute_data(
            transaction_id,
            stripe_amount,
            'lost',
            explanation='Fraudulent transaction. The merchant refused to refund.',
            loss_reason='transaction_authorized',
        )
        self.simulate_webhook_call(event_data)

        self.assertRecordValues(dispute, [{
            'state': 'lost',
            'loss_reason': 'transaction_authorized',
            'explanation': 'Fraudulent transaction. The merchant refused to refund.',
        }])
        mail_domain = [
            ('email_to', '=', self.expense_user_manager.email),
            ('subject', 'ilike', 'Your Dispute for the transaction % Has Been Lost'),
            ('res_id', '=', expense.id),
        ]
        mail = self.env['mail.mail'].sudo().search(mail_domain)
        self.assertEqual(len(mail), 1, "The submitter should be notified when the dispute is lost")
        loss_reason = str(LOSS_REASONS['transaction_authorized']).splitlines()[0]
        self.assertIn(loss_reason, mail.body_html, "The mail should carry the loss reason sent by Stripe")

        # Stripe sends the same event more than once
        self.simulate_webhook_call(event_data)
        self.assertEqual(dispute.state, 'lost')
        self.assertEqual(self.env['mail.mail'].sudo().search_count(mail_domain), 1, "The submitter should not be notified twice")

    def test_dispute_funds_movement_full_amount(self):
        """Statement line amounts match balance_transactions net for a full reinstated/rescinded dispute."""
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)

        amount = 100.0
        stripe_dispute_amount = format_amount_to_stripe(amount, self.stripe_currency)

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -stripe_dispute_amount,
            'authorization': False,
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -stripe_dispute_amount,
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        expense.action_submit()
        expense._do_approve()
        self.post_expenses(expense)

        self.env['hr.expense.stripe.dispute'].sudo().create({
            'stripe_id': 'idp_1234567890',
            'stripe_transaction_id': 'ipi_1234567890',
            'card_id': card.id,
            'currency_id': self.stripe_currency.id,
            'expense_ids': [Command.link(expense.id)],
            'company_id': self.stripe_company.id,
            'amount': amount,
            'reason': 'fraudulent',
        })

        reinstated_event_data = self.get_event_expected_data()
        reinstated_event_data['type'] = 'issuing_dispute.funds_reinstated'
        reinstated_event_data['data']['object'] = {
            'id': 'idp_1234567890',
            'transaction': 'ipi_1234567890',
            'amount': stripe_dispute_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [{'net': stripe_dispute_amount}]},
        }]):
            self.simulate_webhook_call(reinstated_event_data)
        reinstated_line = self.env['account.bank.statement.line'].sudo().search([('stripe_id', '=', 'idp_1234567890'), ('payment_ref', '=', 'Dispute funds reinstated')])
        self.assertRecordValues(reinstated_line, [{'amount': amount, 'payment_ref': 'Dispute funds reinstated', 'state': 'posted'}])

        rescinded_event_data = self.get_event_expected_data()
        rescinded_event_data['type'] = 'issuing_dispute.funds_rescinded'
        rescinded_event_data['data']['object'] = {
            'id': 'idp_1234567890',
            'transaction': 'ipi_1234567890',
            'amount': stripe_dispute_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [{'net': stripe_dispute_amount}, {'net': -stripe_dispute_amount}]},
        }]):
            self.simulate_webhook_call(rescinded_event_data)
        rescinded_line = self.env['account.bank.statement.line'].sudo().search([('stripe_id', '=', 'idp_1234567890'), ('payment_ref', '=', 'Dispute funds rescinded')])
        self.assertRecordValues(rescinded_line, [{'amount': -amount, 'payment_ref': 'Dispute funds rescinded', 'state': 'posted'}])

    def test_dispute_funds_movement_partial_amount(self):
        """Statement line and reversal move reflect balance_transactions net when it differs from dispute amount."""
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)

        expense_amount = 100.0
        reinstated_amount = 95.0
        rescinded_amount = 85.0

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -format_amount_to_stripe(expense_amount, self.stripe_currency),
            'authorization': False,
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -format_amount_to_stripe(expense_amount, self.stripe_currency),
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)
        expense = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        expense.action_submit()
        expense._do_approve()
        self.post_expenses(expense)

        self.env['hr.expense.stripe.dispute'].sudo().create({
            'stripe_id': 'idp_1234567890',
            'stripe_transaction_id': 'ipi_1234567890',
            'card_id': card.id,
            'currency_id': self.stripe_currency.id,
            'expense_ids': [Command.link(expense.id)],
            'company_id': self.stripe_company.id,
            'amount': expense_amount,
            'reason': 'fraudulent',
        })

        stripe_expense_amount = format_amount_to_stripe(expense_amount, self.stripe_currency)

        # Partial reinstated: 95 EUR returned instead of 100
        reinstated_event_data = self.get_event_expected_data()
        reinstated_event_data['type'] = 'issuing_dispute.funds_reinstated'
        reinstated_event_data['data']['object'] = {
            'id': 'idp_1234567890',
            'transaction': 'ipi_1234567890',
            'amount': stripe_expense_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [{'net': format_amount_to_stripe(reinstated_amount, self.stripe_currency)}]},
        }]):
            self.simulate_webhook_call(reinstated_event_data)
        reinstated_line = self.env['account.bank.statement.line'].sudo().search([('stripe_id', '=', 'idp_1234567890'), ('payment_ref', '=', 'Dispute funds reinstated')])
        self.assertRecordValues(reinstated_line, [{'amount': reinstated_amount, 'payment_ref': 'Dispute funds reinstated', 'state': 'posted'}])

        reinstated_reversal = self.env['account.move'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('ref', 'like', 'Reversal of %'),
        ], order='id desc', limit=1)
        outstanding_line = reinstated_reversal.line_ids.filtered(lambda l: l.account_id.reconcile)
        self.assertEqual(len(outstanding_line), 1)
        self.assertAlmostEqual(outstanding_line.balance, reinstated_amount, places=2)

        # Partial rescinded: 85 EUR taken
        rescinded_event_data = self.get_event_expected_data()
        rescinded_event_data['type'] = 'issuing_dispute.funds_rescinded'
        rescinded_event_data['data']['object'] = {
            'id': 'idp_1234567890',
            'transaction': 'ipi_1234567890',
            'amount': stripe_expense_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [
                {'net': format_amount_to_stripe(reinstated_amount, self.stripe_currency)},
                {'net': -format_amount_to_stripe(rescinded_amount, self.stripe_currency)},
            ]},
        }]):
            self.simulate_webhook_call(rescinded_event_data)
        rescinded_line = self.env['account.bank.statement.line'].sudo().search([('stripe_id', '=', 'idp_1234567890'), ('payment_ref', '=', 'Dispute funds rescinded')])
        self.assertRecordValues(rescinded_line, [{'amount': -rescinded_amount, 'payment_ref': 'Dispute funds rescinded', 'state': 'posted'}])

        rescinded_reversal = self.env['account.move'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('ref', 'like', 'Reversal of %'),
        ], order='id desc', limit=1)
        outstanding_line = rescinded_reversal.line_ids.filtered(lambda l: l.account_id.reconcile)
        self.assertEqual(len(outstanding_line), 1)
        self.assertAlmostEqual(outstanding_line.balance, -rescinded_amount, places=2)

    def test_dispute_funds_movement_split_expense_partial(self):
        """Partial movement amounts are distributed proportionally across split-expense disputes.

        This is wrong and we know it. There's no way to know the exact repartition.
        By doing it proportionally, it will create every entry, which the user can modify or delete them
        to reflect the reality.
        """
        card = self.setup_account_creation(funds_amount=10000, create_active_card_for=self.stripe_employee)

        # A second tax to prove each split half can carry different taxes
        tax_21 = self.env['account.tax'].sudo().create({
            'name': "Tax 21%",
            'company_id': self.stripe_company.id,
            'country_id': self.stripe_country.id,
            'tax_group_id': self.stripe_tax.tax_group_id.id,
            'amount': 21,
            'type_tax_use': 'purchase',
        })

        amount1, amount2 = 60.0, 40.0
        reinstated_amount = 95.0
        rescinded_amount = 85.0

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_transaction.created'
        event_data['data']['object'] = {
            'id': 'ipi_1234567890',
            'amount': -format_amount_to_stripe(amount1 + amount2, self.stripe_currency),
            'authorization': False,
            'card': card.stripe_id,
            'created': fields.Datetime.now().timestamp(),
            'merchant_amount': -format_amount_to_stripe(amount1 + amount2, self.stripe_currency),
            'merchant_currency': self.stripe_currency.name.lower(),
            'merchant_data': {
                'category': 'airlines_air_carriers',
                'category_code': '4511',
                'country': self.stripe_country.code.upper(),
                'name': 'Test Merchant',
            },
            'type': 'capture',
        }
        self.simulate_webhook_call(event_data)

        expense1 = self.env['hr.expense'].sudo().search([('stripe_transaction_id', '=', 'ipi_1234567890')])
        wizard = self.env['hr.expense.split.wizard'].browse(expense1.sudo().action_split_wizard()['res_id'])
        # expense1 keeps the original 50% tax; expense2 gets 21%
        wizard.expense_split_line_ids[0].total_amount_currency = amount1
        wizard.expense_split_line_ids[1].total_amount_currency = amount2
        wizard.expense_split_line_ids[1].tax_ids = [Command.set(tax_21.ids)]
        wizard.action_split_expense()
        expense2 = self.env['hr.expense'].sudo().search([
            ('split_expense_origin_id', '=', expense1.id),
            ('id', '!=', expense1.id),
        ])

        for expense in (expense1, expense2):
            expense.action_submit()
            expense._do_approve()
            self.post_expenses(expense)

        self.env['hr.expense.stripe.dispute'].sudo().create({
            'stripe_id': 'idp_1234567890',
            'stripe_transaction_id': 'ipi_1234567890',
            'card_id': card.id,
            'currency_id': self.stripe_currency.id,
            'expense_ids': [Command.link(expense1.id), Command.link(expense2.id)],
            'company_id': self.stripe_company.id,
            'reason': 'fraudulent',
        })
        expense1.disputed_amount = amount1
        expense2.disputed_amount = amount2

        stripe_total_amount = format_amount_to_stripe(amount1 + amount2, self.stripe_currency)

        # Partial reinstated: 95 EUR total → expense1 gets 57, expense2 gets 38
        reinstated_event_data = self.get_event_expected_data()
        reinstated_event_data['type'] = 'issuing_dispute.funds_reinstated'
        reinstated_event_data['data']['object'] = {
            'id': 'idp_1234567890',
            'transaction': 'ipi_1234567890',
            'amount': stripe_total_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [{'net': format_amount_to_stripe(reinstated_amount, self.stripe_currency)}]},
        }]):
            self.simulate_webhook_call(reinstated_event_data)
        reinstated_line = self.env['account.bank.statement.line'].sudo().search([('stripe_id', '=', 'idp_1234567890'), ('payment_ref', '=', 'Dispute funds reinstated')])
        self.assertRecordValues(reinstated_line, [{'amount': reinstated_amount, 'payment_ref': 'Dispute funds reinstated', 'state': 'posted'}])

        reversal1 = self.env['account.move'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('ref', '=', f"Reversal of {expense1.account_move_id.name}"),
        ], limit=1)
        reversal2 = self.env['account.move'].sudo().search([
            ('journal_id', '=', self.stripe_journal.id),
            ('ref', '=', f"Reversal of {expense2.account_move_id.name}"),
        ], limit=1)
        self.assertAlmostEqual(
            reversal1.line_ids.filtered(lambda l: l.account_id.reconcile).balance,
            57.0,  # round(95 * 60/100)
            places=2,
        )
        self.assertAlmostEqual(
            reversal2.line_ids.filtered(lambda l: l.account_id.reconcile).balance,
            38.0,  # 95 - 57
            places=2,
        )

        # Partial rescinded: 85 EUR total → expense1 gets 51, expense2 gets 34
        rescinded_event_data = self.get_event_expected_data()
        rescinded_event_data['type'] = 'issuing_dispute.funds_rescinded'
        rescinded_event_data['data']['object'] = {
            'id': 'idp_1234567890',
            'transaction': 'ipi_1234567890',
            'amount': stripe_total_amount,
            'created': int(fields.Datetime.now().timestamp()),
        }
        with self.patch_stripe_requests('models.account_bank_statement_line', [{
            'route': 'disputes/{dispute_id}',
            'method': 'GET',
            'payload': {'account': 'acct_1234567890', 'expand[0]': 'balance_transactions'},
            'return_data': {'balance_transactions': [
                {'net': format_amount_to_stripe(reinstated_amount, self.stripe_currency)},
                {'net': -format_amount_to_stripe(rescinded_amount, self.stripe_currency)},
            ]},
        }]):
            self.simulate_webhook_call(rescinded_event_data)
        rescinded_line = self.env['account.bank.statement.line'].sudo().search([('stripe_id', '=', 'idp_1234567890'), ('payment_ref', '=', 'Dispute funds rescinded')])
        self.assertRecordValues(rescinded_line, [{'amount': -rescinded_amount, 'payment_ref': 'Dispute funds rescinded', 'state': 'posted'}])

        reversal1 = self.env['account.move'].sudo().search([
            ('id', '!=', reversal1.id),
            ('journal_id', '=', self.stripe_journal.id),
            ('ref', '=', f"Reversal of {expense1.account_move_id.name}"),
        ], limit=1)
        reversal2 = self.env['account.move'].sudo().search([
            ('id', '!=', reversal2.id),
            ('journal_id', '=', self.stripe_journal.id),
            ('ref', '=', f"Reversal of {expense2.account_move_id.name}"),
        ], limit=1)
        self.assertAlmostEqual(
            reversal1.line_ids.filtered(lambda l: l.account_id.reconcile).balance,
            -51.0,  # -round(85 * 60/100)
            places=2,
        )
        self.assertAlmostEqual(
            reversal2.line_ids.filtered(lambda l: l.account_id.reconcile).balance,
            -34.0,  # -(85 - 51)
            places=2,
        )

    #####################################
    #              HELPERS              #
    #####################################
    @classmethod
    def assertIsSubset(cls, expected, actual, msg=None, depth=0):
        """Assert that `actual` contains all key-value pairs in `expected`."""
        errors = []
        if not isinstance(expected, dict) or not isinstance(actual, dict):
            errors.append(f"Both expected and actual must be dictionaries, got {expected.__class__} and {actual.__class__}")

        for key, value in expected.items():
            if key not in actual:
                errors.append(f'Missing key "{key}" in dict')
                continue
            if value == '__ignored__':
                # When we just want to know that the key has a value
                continue
            tested_value = actual[key]
            if isinstance(value, dict) and isinstance(tested_value, dict):
                errors += cls.assertIsSubset(value, tested_value, msg=f'Sub-dict "{key}" error', depth=depth + 1)
            elif value != tested_value:
                errors.append(f'Key "{key}" expected "{value}" as value, {actual[key]}  was found instead')

        if depth > 0:
            if errors:
                return [msg] + errors
            else:
                return []

        if errors:
            raise cls.failureException('\n'.join((msg, *errors)))
        return []

    def patched_make_request_stripe_proxy(self, expected_calls):
        def patched_inner(company, route, route_params=None, payload=None, method="POST", headers=None, files=None, raw=False):
            payload = payload or {}
            if not expected_calls:
                raise ValueError(
                    f"No more calls were expected, but we received: {route} {method} with payload: {payload} for company {company.display_name}"
                )
            expected_call = expected_calls.pop(0)
            self.assertEqual(self.stripe_company.id, company.id)
            self.assertEqual(expected_call.get('route'), route, "Wrong route called")
            self.assertEqual(expected_call.get('method'), method, "Wrong method for request")
            expected_route_params = expected_call.get('route_params')
            if expected_route_params:
                self.assertIsSubset(expected_route_params, route_params, "Wrong route params")
            expected_headers = expected_call.get('headers')
            if expected_headers:
                self.assertDictEqual(expected_headers, headers, "Wrong headers")
            expected_raw = expected_call.get('raw')
            if expected_raw is not None:
                self.assertEqual(expected_raw, raw, "Wrong raw flag")
            expected_files = expected_call.get('files', '__ignored__')
            if expected_files != '__ignored__':
                self.assertEqual(expected_files, files, "Wrong files payload")
            if expected_call.get('payload', '__ignored__') != '__ignored__':
                self.assertIsSubset(
                    expected=expected_call['payload'],
                    actual=payload,
                    msg='Create Stripe connect account request failed with the following errors:',
                )
            return expected_call['return_data']
        return patched_inner

    def patch_stripe_requests(self, method_path, expected_calls):
        """ Helper to patch the stripe request method with expected calls"""
        return patch(
            target=MAKE_STRIPE_REQUEST_PROXY.format(method_path),
            new=self.patched_make_request_stripe_proxy(expected_calls),
        )

    def setup_account_creation(self, funds_amount=0, create_active_card_for=None):
        """ Helper to create the account on the database by mocking required calls

        :param None|float funds_amount: If set, will fund the account with the given amount after creation
        :param None|hr.employee create_active_card_for: If set, will create and activate a virtual card for the given employee after creation
        """
        expected_calls = [
            {
                'route': 'accounts',
                'method': 'POST',
                'payload': {
                    'country': self.stripe_country.code.upper(),
                    'db_public_key': '__ignored__',
                    'db_uuid': '__ignored__',
                    'db_webhook_url': '__ignored__',
                },
                'return_data': {
                    'id': 'acct_1234567890',
                    'iap_public_key': self.iap_key_public_bytes.decode(),
                    'stripe_pk': 'stripe_public_key',
                },
            },
            {
                'route': 'account_links',
                'method': 'POST',
                'payload': {
                    'account': 'acct_1234567890',
                    'refresh_url': '__ignored__',
                    'return_url': '__ignored__',
                },
                'return_data': {
                    'url': 'WWW.SOME.STRIPE.URL',
                },
            },
        ]
        with self.patch_stripe_requests('models.res_company', expected_calls):
            self.stripe_company.with_context(skip_stripe_account_creation_commit=True).action_create_stripe_account()
        if funds_amount:
            self.fund_account(amount=funds_amount)
        if create_active_card_for:
            card = self.create_card(
                card_name='Test Card',
                employee=create_active_card_for,
                create_cardholder=True,
            )
            expected_calls = [{
                'route': 'cards',
                'method': 'POST',
                'payload': '__ignored__',
                'return_data': {
                    'id': 'ic_1234567890',
                    'status': 'active',
                    'type': 'virtual',
                    'cancellation_reason': None,
                    'last4': '1234',
                    'exp_month': 12,
                    'exp_year': 2125,
                    'livemode': False,
                },
            }]
            with self.patch_stripe_requests('models.hr_expense_stripe_card', expected_calls):
                card.action_activate_card()
            return card
        return self.env['hr.expense.stripe.card']

    def fund_account(self, amount=100000.0):
        """ Helper to quickly fund the account on the database by mocking required calls """
        self.simulate_webhook_call(
            self.get_event_balance_updated_data(format_amount_to_stripe(amount, self.stripe_currency))
        )
        self.simulate_webhook_call(
            self.get_event_topup_succeeded_updated_data(format_amount_to_stripe(amount, self.stripe_currency))
        )

    def create_cardholder(self, card, employee):
        """ Helper to quickly create a cardholder on the database by mocking required calls """
        action = card.sudo().action_open_cardholder_wizard()
        wizard = (
            self.env['hr.expense.stripe.cardholder.wizard']
            .with_context(action['context'])
            .with_user(self.expense_user_manager)
            .browse(action['res_id'])
        )
        wizard.phone_number = '+32000000000'

        expected_calls = [{
            'route': 'cardholders',
            'method': 'POST',  # Even though it's technically a GET request, it generates the new data on Stripe if updated
            'payload': '__ignored__',
            'return_data': {
                'id': 'ich_1234567890',
                'livemode': False,
            },
        }]
        with (
            self.patch_stripe_requests('wizard.hr_expense_stripe_cardholder_wizard', expected_calls),
            patch.object(phone_validation, 'phone_format', new=lambda *args, **kwargs: "+32000000000"),
        ):
            wizard.action_save_cardholder()

    def create_card(self, card_name='Test Card', country_ids=False, mcc_ids=False, employee=None, create_cardholder=True, **kwargs):
        """ Helper to quickly create a card on the database by mocking required calls """
        card_create_vals = {
            'employee_id': (employee or self.stripe_employee).id,
            'name': card_name,
            'company_id': self.env.company.id,
            **kwargs,
        }
        if kwargs.get('card_type') == 'physical':
            if employee and employee.address_id:
                card_create_vals['delivery_address_id'] = employee.sudo().address_id.id
            else:
                card_create_vals['delivery_address_id'] = self.stripe_employee.sudo().address_id.id
        if country_ids:
            card_create_vals['spending_policy_country_tag_ids'] = [Command.set(country_ids)]
        if mcc_ids:
            card_create_vals['spending_policy_category_tag_ids'] = [Command.set(mcc_ids)]
        card = self.env['hr.expense.stripe.card'].with_user(self.expense_user_manager).create([card_create_vals])
        if create_cardholder:
            self.create_cardholder(card=card, employee=employee)
        return card

    def simulate_card_shipping(self, card, status=None, tracking_number=None, tracking_url=None, eta=None, previous_shipping_status=None):
        """ Helper to simulate shipping updates from Stripe """
        if card.card_type != 'physical':
            raise ValueError("Can only simulate shipping for physical cards")

        event_data = self.get_event_expected_data()
        event_data['type'] = 'issuing_card.updated'
        event_data['data']['object'] = {
            'id': card.stripe_id,
            'object': 'issuing.card',
            'cancellation_reason': card.cancellation_reason,
            'shipping': {
                'status': status or card.shipping_status,
                'tracking_number': tracking_number or card.tracking_number,
                'tracking_url': tracking_url or card.tracking_url,
                'eta': eta or (card.shipping_estimated_delivery and int(card.shipping_estimated_delivery.timestamp())),
            },
            'livemode': False,
            'status': card.state if card.state != 'pending' else 'inactive',
            'type': 'physical',
        }
        event_data['data']['previous_attributes'] = {
            'shipping': {
                'status': previous_shipping_status or card.shipping_status,
            }
        }
        self.simulate_webhook_call(event_data)

    @info_as_debug('odoo.addons.hr_expense_stripe.controllers.main')
    def simulate_webhook_call(self, stripe_data, company_uuid=None):
        """ Helper to mock a webhook call to the controller """
        result = {}

        def make_json_response(data, **kwargs):
            result.update({'content': data, **kwargs})
            return json.dumps({'content': data}.update(kwargs))

        company_uuid = company_uuid or self.stripe_company.stripe_issuing_iap_webhook_uuid
        with MockRequest(self.env, path=f'/stripe_issuing/webhook/{company_uuid}') as request:
            request.httprequest.method = 'POST'
            request.httprequest.data = str(stripe_data).encode()
            request.httprequest.headers = {
                'Stripe-Signature': f'signature={self.iap_key_public_bytes.decode()}',
                'Iap-Signature': 'signature=1234',
                'Content-Type': 'application/json',
            }

            request.get_json_data = lambda: stripe_data
            request.make_json_response = make_json_response
            request.is_frontend = False
            self.Controller.stripe_issuing_webhook(company_uuid)
        return result

    def get_event_expected_data(self, account=None, timestamp=0):
        """ helper to get the base event data structure, only contains the important fields """
        account = account or self.stripe_company.stripe_id
        return {
            'id': f'evt_{account}1234567890',
            'account': account,
            'object': 'event',
            'api_version': '2025-01-27.acacia',
            'created': timestamp or datetime.datetime.now().timestamp(),
            'data': {
                'object': {}  # TO FILL
            },
            'livemode': False,
            'pending_webhooks': 1,
            'request': {'id': False, 'idempotency_key': False},
            'type': False,  # TO FILL
        }

    def get_event_balance_updated_data(self, amount, account=None, currency=None, timestamp=0):
        """ helper to get a `balance.available` event data structure, only contains the important fields """
        account = account or self.stripe_company.stripe_id
        currency = currency or self.stripe_currency.name
        event_data = self.get_event_expected_data(account, timestamp)
        event_data['type'] = 'balance.available'
        event_data['data']['object'] = {
            'object': 'balance',
            'available': [{'amount': 0, 'currency': currency, 'source_types': {}}],
            'instant_available': [{'amount': 0, 'currency': currency, 'source_types': {}}],
            'issuing': {'available': [{'amount': amount, 'currency': currency}]},
            'livemode': False,
            'pending': [{'amount': 0, 'currency': currency, 'source_types': {}}],
            'refund_and_dispute_prefunding': {
                'available': [{'amount': 0, 'currency': currency}],
                'pending': [{'amount': 0, 'currency': currency}],
            }
        }
        return event_data

    def get_stripe_dispute_data(self, transaction_id, amount, status, reason='fraudulent', explanation=None, loss_reason=None):
        """ helper to get an `issuing.dispute` object, only contains the important fields """
        dispute_object = {
            'id': 'idp_1234567890',
            'amount': amount,
            'currency': self.stripe_currency.name.lower(),
            'transaction': transaction_id,
            'status': status,
            'evidence': {'reason': reason, reason: {'explanation': explanation} if explanation else {}},
        }
        if loss_reason:
            dispute_object['loss_reason'] = loss_reason
        return dispute_object

    def get_event_topup_succeeded_updated_data(self, amount, account=None, currency=None, timestamp=0):
        """ helper to get a `topup.succeeded` event data structure, only contains the important fields """
        account = account or self.stripe_company.stripe_id
        currency = currency or self.stripe_currency.name
        event_data = self.get_event_expected_data(account, timestamp)
        event_data['type'] = 'topup.succeeded'
        event_data['data']['object'] = {
            'id': 'tu_12345678901234567890',
            'object': 'topup',
            'amount': amount,
            'balance_transaction': 'txn_12345678901234567890',
            'created': timestamp,
            'currency': currency,
            'expected_availability_date': timestamp,
            'livemode': False,
            'metadata': {},
            'source': {},
            'statement_descriptor': None,
            'status': 'succeeded',
            'transfer_group': None,
            'destination_balance': 'issuing',
        }
        return event_data
