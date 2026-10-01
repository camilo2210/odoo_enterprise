from freezegun import freeze_time
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, RedirectWarning, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user
from odoo.tools import mute_logger
from odoo.addons.account_direct_debit.tests.common import AccountDirectDebitCommon


@tagged('post_install', '-at_install')
class TestDirectDebitMandate(AccountDirectDebitCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Fake a "test_dd" mandate type for generic tests
        mandate_type_field = cls.env['account.direct.debit.mandate']._fields['mandate_type']
        old_selection = mandate_type_field.selection
        old_internal_selection = mandate_type_field._selection
        if ('test_dd', 'Test Direct Debit') not in old_selection:
            mandate_type_field.selection = list(old_selection) + [('test_dd', 'Test Direct Debit')]
            mandate_type_field._selection = set(old_internal_selection or ()) | {'test_dd'}
            cls.addClassCleanup(setattr, mandate_type_field, 'selection', old_selection)
            cls.addClassCleanup(setattr, mandate_type_field, '_selection', old_internal_selection)
        patcher_type = patch(
            'odoo.addons.account_direct_debit.models.account_payment_method.AccountPaymentMethod._get_mandate_type_per_code',
            return_value={'test_dd': 'test_dd'},
        )
        patcher_type.start()
        cls.addClassCleanup(patcher_type.stop)

        cls.payment_method_test = cls.env['account.payment.method'].sudo().create({
            'name': 'Test Direct Debit',
            'code': 'test_dd',
            'payment_type': 'inbound',
        })
        cls.payment_method_line = cls.env['account.payment.method.line'].sudo().create({
            'name': 'Test Direct Debit',
            'payment_method_id': cls.payment_method_test.id,
            'journal_id': cls.journal.id,
        })

        cls.non_validator_user = new_test_user(
            cls.env,
            login='non_validator_user',
            groups='account.group_account_invoice',
        )

    @freeze_time('2024-12-01')
    def test_mandate_defaults_and_computes(self):
        partner_a_child = self.env['res.partner'].create({
            'name': 'Partner A Child',
            'parent_id': self.partner_a.id,
        })
        mandate = self._create_mandate(
            validate=False,
            mandate_type='test_dd',
            partner_id=partner_a_child.id,
            partner_bank_id=False,
        )

        self.assertEqual(mandate.start_date, fields.Date.today())
        self.assertEqual(mandate.pre_notification_period, 2)
        self.assertEqual(mandate.state, 'draft')
        self.assertEqual(mandate.display_name, 'Partner A Child')

        mandate.end_date = '2025-12-31'
        self.assertEqual(mandate.display_name, 'Partner A Child - 12/31/2025')

        self.assertIn('not_commercial_partner', mandate.alerts)
        self.assertEqual(mandate.alerts['not_commercial_partner']['level'], 'warning')

    @mute_logger('odoo.sql_db')
    def test_mandate_constraints(self):
        # End date < Start date
        with self.assertRaisesRegex(UserError, "The end date of the mandate must be posterior or equal to its start date."):
            self._create_mandate(
                validate=False,
                mandate_type='test_dd',
                start_date='2025-06-01',
                end_date='2025-05-01',
            )

        # Pre-notification period violated
        mandate = self._create_mandate(validate=False, mandate_type='test_dd')
        with self.assertRaisesRegex(UserError, "The pre-notification period must be at least"):
            mandate.pre_notification_period = 1

        # Partner and bank account mismatch
        with self.assertRaisesRegex(ValidationError, "Mandate customer and bank account need to match."):
            self._create_mandate(
                validate=False,
                mandate_type='test_dd',
                partner_bank_id=self.comp_bank_account1.id,
            )

    def test_payment_mandate_constraints(self):
        today = fields.Date.today()
        mandate = self._create_mandate(mandate_type='test_dd', start_date=today, end_date=fields.Date.add(today, days=30))
        payment_vals = {
            'payment_type': 'inbound',
            'partner_id': self.partner_a.id,
            'amount': 100.0,
            'date': today,
            'payment_method_line_id': self.payment_method_line.id,
            'mandate_id': mandate.id,
        }
        self.env['account.payment'].create(payment_vals)

        # The mandate must belong to the payment's customer
        with self.assertRaisesRegex(ValidationError, "mandate belonging to a different partner"):
            self.env['account.payment'].create({**payment_vals, 'partner_id': self.partner_b.id})

        # The mandate must cover the payment method
        with self.assertRaisesRegex(ValidationError, "cannot be used to collect"):
            self.env['account.payment'].create({**payment_vals, 'payment_method_line_id': self.inbound_payment_method_line.id})

        # The mandate must be valid at the payment date
        with self.assertRaisesRegex(ValidationError, "is not valid on"):
            self.env['account.payment'].create({**payment_vals, 'date': fields.Date.add(today, days=60)})

        # The bank account to collect from must be the one authorized by the mandate, not just any
        # bank account belonging to the same partner.
        with self.assertRaisesRegex(ValidationError, "must be the one authorized by the mandate"):
            self.env['account.payment'].create({**payment_vals, 'return_partner_bank_id': self.partner_bank_account2.id})

    def test_mandate_state_transitions_and_access(self):
        countryless_partner = self.env['res.partner'].create({'name': 'Stateless Customer'})
        mandate = self._create_mandate(
            validate=False,
            mandate_type='test_dd',
            partner_id=countryless_partner.id,
            partner_bank_id=False,
        )

        # Non-bank validator user raises AccessError on validation
        with self.assertRaisesRegex(AccessError, "You don't have the rights to validate direct debit mandates."):
            mandate.with_user(self.non_validator_user).action_validate_mandate()

        # Countryless partner raises RedirectWarning
        with self.assertRaisesRegex(RedirectWarning, "The customer must have a country"):
            mandate.action_validate_mandate()

        # Missing bank account raises UserError
        countryless_partner.country_id = self.quick_ref('base.be')
        with self.assertRaisesRegex(UserError, "A customer bank account is required to validate a direct debit mandate."):
            mandate.action_validate_mandate()

        # Untrusted bank account raises RedirectWarning
        bank_account = self.env['res.partner.bank'].create({
            'account_number': 'BE58465045170210',
            'partner_id': countryless_partner.id,
            'allow_out_payment': False,
        })
        mandate.partner_bank_id = bank_account
        with self.assertRaisesRegex(RedirectWarning, "must be trusted before it can be used"):
            mandate.action_validate_mandate()

        # A user without the rights to trust the bank account gets a different message
        with self.assertRaisesRegex(RedirectWarning, "Ask your administrator to trust it"):
            mandate.with_user(self.non_validator_user)._check_bank_account_for_validation()

        # Trust the bank account and validate successfully
        bank_account.allow_out_payment = True
        mandate.action_validate_mandate()
        self.assertEqual(mandate.state, 'active')

        # Deleting non-draft mandate raises UserError
        with self.assertRaisesRegex(UserError, "Only draft mandates can be deleted."):
            mandate.unlink()

        # Revoke mandate
        mandate.action_revoke_mandate()
        self.assertEqual(mandate.state, 'revoked')

        # Cancel mandate
        mandate2 = self._create_mandate(validate=False, mandate_type='test_dd')
        mandate2.action_cancel_mandate()
        self.assertEqual(mandate2.state, 'cancelled')

        # Close mandate
        mandate3 = self._create_mandate(mandate_type='test_dd')
        mandate3.action_close_mandate()
        self.assertEqual(mandate3.state, 'closed')
        self.assertEqual(mandate3.end_date, fields.Date.today())

        # Unlink draft mandate succeeds
        draft_mandate = self._create_mandate(validate=False, mandate_type='test_dd')
        draft_mandate.unlink()

    def test_usable_mandate_lookup_and_invoice_search(self):
        today = fields.Date.today()
        mandate = self._create_mandate(mandate_type='test_dd', start_date=today)

        found_mandate = self.env['account.direct.debit.mandate']._get_usable_mandate(
            self.company.id,
            self.partner_a.id,
            today,
        )
        self.assertEqual(found_mandate, mandate)

        # Invoice has_usable_mandate test
        invoice = self._create_invoice(invoice_date=today)
        self.assertTrue(invoice.has_usable_mandate)

        # Search domain for invoices with usable mandate
        matching_invoices = self.env['account.move'].search([('has_usable_mandate', '=', True)])
        self.assertIn(invoice, matching_invoices)

        non_matching_invoices = self.env['account.move'].search([('has_usable_mandate', '=', False)])
        self.assertNotIn(invoice, non_matching_invoices)

    @freeze_time('2025-01-01')
    def test_mandate_validity_and_expiration(self):
        mandate = self._create_mandate(mandate_type='test_dd', start_date='2025-01-01', end_date='2025-06-30')

        partition = mandate._update_and_partition_state_by_validity()
        self.assertEqual(partition, {'valid': mandate})

        with freeze_time('2025-06-15'):
            partition = mandate._update_and_partition_state_by_validity()
            self.assertEqual(partition, {'expiring': mandate})

        with freeze_time('2025-07-01'):
            partition = mandate._update_and_partition_state_by_validity()
            self.assertEqual(partition, {'invalid': mandate})
            self.assertEqual(mandate.state, 'closed')

    def test_partner_smart_button_and_bank_unlink_protection(self):
        mandate = self._create_mandate(mandate_type='test_dd')
        self.assertIn(mandate, self.partner_a.mandate_ids)
        self.assertEqual(self.partner_a.mandate_count, 1)

        open_action = self.partner_a.action_open_mandates()
        self.assertEqual(open_action['domain'], [('partner_id', '=', self.partner_a.id)])

        # Bank unlink protection
        with self.assertRaisesRegex(UserError, "You cannot delete a bank account linked to an active Direct Debit Mandate."):
            mandate.partner_bank_id.sudo().unlink()

    def test_mandate_end_date_inclusive(self):
        end_date = '2025-06-30'
        self._create_mandate(mandate_type='test_dd', start_date='2025-01-01', end_date=end_date)

        invoice = self._create_invoice(invoice_date=end_date)
        self.assertTrue(invoice.has_usable_mandate)
        self.assertIn(invoice, self.env['account.move'].search([('has_usable_mandate', '=', True)]))

    def test_one_off_mandate_closure_on_payment_paid(self):
        mandate = self._create_mandate(mandate_type='test_dd', one_off=True)
        invoice = self._create_invoice(post=True)
        self.assertEqual(mandate.state, 'active')

        payment = self._register_payment(invoice, payment_method_line_id=self.payment_method_line.id)
        self.assertEqual(payment.mandate_id, mandate)
        self.assertEqual(mandate.state, 'closed')

    def test_payment_register_child_partner_mandate(self):
        # The mandate of the commercial partner covers the invoices of its children
        partner_a_child = self.env['res.partner'].create({
            'name': 'Partner A Child',
            'parent_id': self.partner_a.id,
        })
        mandate = self._create_mandate(mandate_type='test_dd')
        invoice = self._create_invoice(partner_id=partner_a_child, post=True)
        payment = self._register_payment(invoice, payment_method_line_id=self.payment_method_line.id)

        self.assertEqual(payment.mandate_id, mandate)
        self.assertIn(invoice.payment_state, ('in_payment', 'paid'))
