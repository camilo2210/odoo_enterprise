from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged, patch
from odoo.addons.account.tools.structured_reference import is_valid_structured_reference_for_country
from odoo.addons.account_online_synchronization.tests.common import AccountOnlineSynchronizationCommon


def _patch_initiate_payment(self, records):
    for record in records:
        record.write({
            'payment_identifier': 'id1234',
            'payment_online_status': 'accepted',
        })

    return {
        'type': 'ir.actions.act_url',
        'url': '/',
        'target': '_blank',
    }


def _patch_fetch_status_rejected(self, url, data=None, ignore_status=False):
    # Simulates Odoofin answering that the payment was rejected by the bank.
    return {'payment_online_status': 'rejected'}


def _patch_fetch_status_canceled(self, url, data=None, ignore_status=False):
    return {'payment_online_status': 'canceled'}


def _patch_fetch_unsigned(self, url, data=None, ignore_status=False):
    return {
        'payment_identifier': 'id1234',
        'payment_online_status': 'unsigned',
        'redirect_url': '/',
    }


def _patch_fetch_accepted(self, url, data=None, ignore_status=False):
    return {
        'payment_identifier': 'id1234',
        'payment_online_status': 'accepted',
        'redirect_url': '/',
    }


def _patch_check_payment_limit_exceeded_good(self, payments):
    return True


@tagged('post_install', '-at_install')
class TestAccountOnlinePaymentBatch(AccountOnlineSynchronizationCommon):
    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account_online_link.is_payment_enabled = True
        cls.account_online_link.is_payment_activated = True

        cls.partner_bank = cls.env['res.partner.bank'].create({
            'account_number': 'BE68539007547034',
            'account_type': 'iban',
            'allow_out_payment': True,
            'partner_id': cls.partner.id,
        })

        cls.company_bank = cls.env['res.partner.bank'].create({
            'account_number': 'BE32707171912447',
            'account_type': 'iban',
            'partner_id': cls.env.company.partner_id.id,
        })
        cls.euro_bank_journal.bank_account_id = cls.company_bank

        sepa_ct = cls.env.ref('account_iso20022.account_payment_method_sepa_ct')
        cls.sepa_method_line = cls.euro_bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.payment_method_id == sepa_ct,
        )[0]
        cls.manual_method_line = cls.euro_bank_journal.outbound_payment_method_line_ids.filtered(
            lambda line: line.code == 'manual',
        )[0]

    def _create_payment(self, payment_method_line=None, amount=1, **values):
        payment_method_line = payment_method_line or self.sepa_method_line
        payment_vals = {
            'partner_id': self.partner.id,
            'partner_bank_id': self.partner_bank.id,
            'amount': amount,
            'payment_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_line_id': payment_method_line.id,
            'currency_id': self.ref('base.EUR'),
        }
        payment_vals.update(values)
        return self.env['account.payment'].create(payment_vals)

    @patch('odoo.addons.account_online_payment.models.account_payment.is_valid_structured_reference_for_country', side_effect=is_valid_structured_reference_for_country)
    def test_prepare_payment_data(self, mock):
        """
        IMPORTANT: The idea behind this test is to ensure that Enterprise and Odoofin communicate correctly.

        If this test breaks, it doesn't necessarily mean that the code in account_online_payment is wrong,
        but rather that the data being sent to Odoofin has changed and Odoofin might need to be updated to
        handle the new data structure.

        If that is the case, please update Odoofin's side to handle the new data structure.
        """
        payment = self._create_payment(amount=100.0)
        payment.action_post()

        batch = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_ids': [Command.set(payment.ids)],
        })

        # This call would raise AttributeError if the wrong field
        # (sanitized_acc_number) were used instead of sanitized_account_number
        # which could easily happen during the forward port of a PR.
        self.partner.vat = 'vat'
        self.partner.contact_address_inline = 'contact_address_inline'
        batch.journal_id.company_id.vat = 'vat'

        data = batch._prepare_payment_data()

        self.assertEqual(data, {
            'account_id': self.account_online_account.online_identifier,
            'batch_booking': batch.iso20022_batch_booking,
            'date': fields.Date.to_string(batch.date),
            'payer_account_number': batch.journal_id.account_online_account_id.account_number,
            'payer_account_type': 'iban',
            'payer_account_holder_name': 'company_1_data',
            'payer_address': batch.journal_id.company_id.partner_id.contact_address_inline,
            'payer_name': batch.journal_id.company_id.name,
            'payer_identification': batch.journal_id.company_id.vat,
            'payment_type': "bulk",
            'payments': [{
                'amount': 100.0,
                'account_number': self.partner_bank.sanitized_account_number,
                'account_type': 'IBAN',
                'creditor_address': 'contact_address_inline',
                'creditor_identification': 'vat',
                'creditor_name': self.partner.name,
                'currency': payment.currency_id.display_name,
                'date': fields.Date.to_string(payment.date),
                'reference': payment.memo,
                'structured_reference': is_valid_structured_reference_for_country(payment.memo, 'BE'),
                'transaction_uuid': payment.transaction_uuid,
            }],
            'reference': batch.name,
        })
        mock.assert_called_once_with(payment.memo, 'BE')

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._initiate_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_init_multiple_bills(self):
        bill_1, bill_2 = self.env['account.move'].create([{
            'partner_id': self.partner.id,
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'currency_id': self.ref('base.EUR'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Product',
                    'price_unit': 1,
                    'quantity': 1,
                    'tax_ids': [],
                })
            ]
        }, {
            'partner_id': self.partner.id,
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'currency_id': self.ref('base.EUR'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Product',
                    'price_unit': 1,
                    'quantity': 1,
                    'tax_ids': [],
                })
            ]
        }])
        (bill_1 | bill_2).action_post()
        payment_register_wizard = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=(bill_1 | bill_2).ids).create({
            'journal_id': self.euro_bank_journal.id,
        })
        self.assertTrue(payment_register_wizard.could_initiate_payment)
        payment_register_wizard.action_create_payments()
        payments = self.env['account.payment'].search([('reconciled_bill_ids', 'in', (bill_1 | bill_2).ids)])
        batch_payment = self.env['account.batch.payment'].search([('payment_ids', 'in', payments.ids)])
        self.assertEqual(set(payments.mapped('state')), {'paid'})
        self.assertRecordValues(batch_payment, [
            {'payment_identifier': 'id1234', 'payment_online_status': 'accepted'},
        ])

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._initiate_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_init_single_bill(self):
        bill = self.env['account.move'].create({
            'partner_id': self.partner.id,
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'currency_id': self.ref('base.EUR'),
            'invoice_line_ids': [
                Command.create({
                    'name': 'Product',
                    'price_unit': 1,
                    'quantity': 1,
                    'tax_ids': [],
                })
            ]
        })
        bill.action_post()
        payment_register_wizard = self.env['account.payment.register'].with_context(active_model='account.move', active_ids=bill.ids).create({
            'journal_id': self.euro_bank_journal.id,
        })
        self.assertTrue(payment_register_wizard.could_initiate_payment)
        payment_register_wizard.action_create_payments()
        payment = self.env['account.payment'].search([('reconciled_bill_ids', 'in', bill.ids)])
        self.assertFalse(payment.batch_payment_id)
        self.assertRecordValues(payment, [
            {'payment_identifier': 'id1234', 'payment_online_status': 'accepted', 'state': 'paid'},
        ])

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._initiate_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_init_multiple_payments(self):
        payment_1 = self._create_payment()
        payment_2 = self._create_payment()
        payments = (payment_1 | payment_2)
        payments.action_pay()
        batch_payment = self.env['account.batch.payment'].search([('payment_ids', 'in', payments.ids)])
        self.assertEqual(set(payments.mapped('state')), {'paid'})
        self.assertRecordValues(batch_payment, [
            {'payment_identifier': 'id1234', 'payment_online_status': 'accepted'},
        ])

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._initiate_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_init_single_payment(self):
        payment = self._create_payment()
        payment.action_pay()
        self.assertFalse(payment.batch_payment_id)
        self.assertRecordValues(payment, [
            {'payment_identifier': 'id1234', 'payment_online_status': 'accepted', 'state': 'paid'},
        ])

    def test_init_payment_not_allowed(self):
        payment = self._create_payment()
        self.account_online_link.is_payment_activated = False
        with self.assertRaisesRegex(UserError, r"The payment initiation service is not activated for this journal\."):
            payment.action_pay()

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._initiate_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_pay_resets_selected_payments_from_unsent_batch(self):
        """Only selected payments are removed from an unsigned batch before retrying."""
        payment = self._create_payment()
        unselected_payment = self._create_payment()
        batch = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_id': self.sepa_method_line.payment_method_id.id,
            'payment_ids': [Command.set((payment | unselected_payment).ids)],
        })
        batch.payment_online_status = 'unsigned'
        payment.is_sent = True
        self.assertEqual(payment.batch_payment_id, batch)

        payment.action_pay()

        self.assertFalse(payment.batch_payment_id, "The payment should have been detached from its batch.")
        self.assertEqual(batch.payment_ids, unselected_payment)
        self.assertFalse(payment.is_sent, "The sent flag should have been reset for the retry.")
        self.assertRecordValues(payment, [
            {'payment_identifier': 'id1234', 'payment_online_status': 'accepted', 'state': 'paid'},
        ])

    def test_pay_rejects_payments_in_sent_batch(self):
        """A payment in a batch already sent to the bank cannot be re-initiated."""
        payment = self._create_payment()
        batch = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_id': self.sepa_method_line.payment_method_id.id,
            'payment_ids': [Command.set(payment.ids)],
        })
        batch.payment_online_status = 'accepted'

        with self.assertRaisesRegex(UserError, r"Only uninitiated or unsigned payments can be retried."):
            payment.action_pay()

    @patch(
        'odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin',
        new=_patch_fetch_status_rejected,
    )
    def test_check_status_marks_payment_rejected(self):
        """A rejected/canceled online status flips the payment to the 'rejected' state."""
        payment = self._create_payment()
        payment._generate_journal_entry()
        payment.payment_identifier = 'id1234'

        statuses = self.env['account.online.link'].check_online_payment_status(payment.ids, 'account.payment')

        self.assertEqual(statuses[payment.id], 'rejected')
        self.assertEqual(payment.payment_online_status, 'rejected')
        self.assertEqual(payment.state, 'rejected')

    @patch(
        'odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin',
        new=_patch_fetch_status_canceled,
    )
    def test_check_status_marks_payment_canceled(self):
        payment = self._create_payment()
        payment._generate_journal_entry()
        payment.payment_identifier = 'id1234'

        statuses = self.env['account.online.link'].check_online_payment_status(payment.ids, 'account.payment')

        self.assertEqual(statuses[payment.id], 'canceled')
        self.assertEqual(payment.payment_online_status, 'canceled')
        self.assertEqual(payment.state, 'canceled')

    def test_batch_online_status_write_syncs_payment_states(self):
        payments = self._create_payment() | self._create_payment()
        batch = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_id': self.sepa_method_line.payment_method_id.id,
            'payment_ids': [Command.set(payments.ids)],
        })

        batch.payment_online_status = 'accepted'

        self.assertEqual(batch.payment_online_status, 'accepted')
        self.assertEqual(payments.mapped('state'), ['paid', 'paid'])

    @patch(
        'odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin',
        new=_patch_fetch_unsigned,
    )
    def test_initiate_payment_marks_unsigned_payment_draft(self):
        payment = self._create_payment()
        self.env['account.online.link']._initiate_payment(payment)

        self.assertEqual(payment.payment_online_status, 'unsigned')
        self.assertEqual(payment.state, 'draft')

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._sign_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_pay_routes_single_unsigned_payment_to_signing(self):
        payment = self._create_payment()
        payment.write({
            'payment_identifier': 'id1234',
            'payment_online_status': 'unsigned',
        })

        payment.action_pay()

        self.assertRecordValues(payment, [{
            'payment_identifier': 'id1234',
            'payment_online_status': 'accepted',
        }])

    @patch('odoo.addons.account_online_payment.models.account_online_link.AccountOnlineLink._initiate_payment', new=_patch_initiate_payment)
    @patch('odoo.addons.account_online_payment.models.account_online_account.AccountOnlineAccount._check_payment_limit_exceeded', new=_patch_check_payment_limit_exceeded_good)
    def test_pay_retries_multiple_unsigned_payments_in_new_batch(self):
        unsigned_payments = self._create_payment() | self._create_payment()
        uninitiated_payment = self._create_payment()
        unsigned_payments.write({
            'is_sent': True,
            'payment_identifier': 'id1234',
            'payment_online_status': 'unsigned',
        })

        payments = unsigned_payments | uninitiated_payment
        payments.action_pay()

        batch = payments.batch_payment_id
        self.assertEqual(len(batch), 1)
        self.assertRecordValues(unsigned_payments, [{
            'is_sent': False,
            'payment_identifier': False,
            'payment_online_status': 'uninitiated',
        }, {
            'is_sent': False,
            'payment_identifier': False,
            'payment_online_status': 'uninitiated',
        }])
        self.assertRecordValues(uninitiated_payment, [{
            'is_sent': False,
            'payment_identifier': False,
            'payment_online_status': 'uninitiated',
        }])
        self.assertRecordValues(batch, [{
            'payment_identifier': 'id1234',
            'payment_online_status': 'accepted',
        }])

    @patch(
        'odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._fetch_odoo_fin',
        new=_patch_fetch_accepted,
    )
    def test_sign_payment_marks_accepted_payment_paid(self):
        payment = self._create_payment()
        payment._generate_journal_entry()
        payment.action_draft()
        payment.payment_identifier = 'id1234'
        payment.payment_online_status = 'unsigned'

        self.env['account.online.link']._sign_payment(payment)

        self.assertEqual(payment.payment_online_status, 'accepted')
        self.assertEqual(payment.state, 'paid')

    def test_payment_action_buttons_exportable_method_activated_journal(self):
        payment = self._create_payment(payment_method_line=self.sepa_method_line)
        self.assertTrue(payment.could_initiate_payment)
        self.assertTrue(payment.show_download_xml_button)
        self.assertFalse(payment.show_connect_bank_button)
        self.assertFalse(payment.show_activate_payments_button)

    def test_payment_action_buttons_exportable_method_non_activated_journal(self):
        self.account_online_link.is_payment_activated = False
        payment = self._create_payment(payment_method_line=self.sepa_method_line)
        self.assertFalse(payment.could_initiate_payment)
        self.assertTrue(payment.show_download_xml_button)
        self.assertFalse(payment.show_connect_bank_button)
        self.assertTrue(payment.show_activate_payments_button)

    def test_payment_action_buttons_non_enabled_payment_service(self):
        self.account_online_link.is_payment_activated = False
        self.account_online_link.is_payment_enabled = False
        payment = self._create_payment(payment_method_line=self.sepa_method_line)
        self.assertFalse(payment.could_initiate_payment)
        self.assertTrue(payment.show_download_xml_button)
        self.assertTrue(payment.show_connect_bank_button)
        self.assertFalse(payment.show_activate_payments_button)

    def test_payment_action_buttons_non_exportable_method(self):
        payment = self._create_payment(payment_method_line=self.manual_method_line)
        self.assertTrue(payment.could_initiate_payment)
        self.assertFalse(payment.show_download_xml_button)
        self.assertFalse(payment.show_connect_bank_button)
        self.assertFalse(payment.show_activate_payments_button)

    @patch('odoo.addons.account_online_synchronization.models.account_online.AccountOnlineLink._get_institution_data')
    def test_payment_limit(self, patched_institution_data):
        patched_institution_data.return_value = {
            'payment_institution': {
                'institution_payment_max_amount_limit': 10000,
                'institution_payment_instructions_limit': 10,
            },
        }

        # Valid case
        payments = self.env['account.payment'].create([{
            'partner_id': self.partner.id,
            'partner_bank_id': self.partner_bank.id,
            'amount': 100.0,
            'payment_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_line_id': self.sepa_method_line.id,
        } for _ in range(5)])
        payments.action_post()

        batch_500 = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_ids': [Command.set(payments.ids)],
        })

        batch_500.journal_id.account_online_account_id._check_payment_limit_exceeded(batch_500.payment_ids)
        patched_institution_data.assert_called_once()

        # Max amount exceeded on batch
        payments = self.env['account.payment'].create([{
            'partner_id': self.partner.id,
            'partner_bank_id': self.partner_bank.id,
            'amount': 3000.0,
            'payment_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_line_id': self.sepa_method_line.id,
        } for _ in range(5)])
        payments.action_post()

        batch_15000 = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_ids': [Command.set(payments.ids)],
        })
        with self.assertRaises(UserError):
            batch_15000.validate_batch(initiate_payment=True)

        # Max number of payments exceeded
        payments = self.env['account.payment'].create([{
            'partner_id': self.partner.id,
            'partner_bank_id': self.partner_bank.id,
            'amount': 50.0,
            'payment_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_method_line_id': self.sepa_method_line.id,
        } for _ in range(20)])
        payments.action_post()

        batch_1000 = self.env['account.batch.payment'].create({
            'batch_type': 'outbound',
            'journal_id': self.euro_bank_journal.id,
            'payment_ids': [Command.set(payments.ids)],
        })
        with self.assertRaises(UserError):
            batch_1000.validate_batch(initiate_payment=True)
