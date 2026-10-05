from odoo import exceptions
from odoo.addons.whatsapp.tests.common import WhatsAppCommon, MockOutgoingWhatsApp
from odoo.tests import tagged, users


class WhatsAppBlocklistCommon(WhatsAppCommon, MockOutgoingWhatsApp):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def _update_block_status(action, numbers):
            return {
                'updated_numbers': set(numbers),
                'failures': {},
            }

        with cls.mockWhatsappBlockStatus(_update_block_status):
            cls.all_blocklist_records = (
                cls.acc1_unblocked_ok, cls.acc1_unblocked_fail, cls.acc1_blocked_ok, cls.acc1_blocked_fail,
                cls.acc1_unblocked_neither, cls.acc1_blocked_neither,
                cls.acc2_unblocked_ok, cls.acc2_unblocked_fail, cls.acc2_blocked_ok, cls.acc2_blocked_fail,
                cls.acc2_unblocked_neither, cls.acc2_blocked_neither,
            ) = cls.env['whatsapp.blocklist'].create([
                {'number': '+911234567891', 'wa_account_id': cls.whatsapp_account.id, 'active': False},    # acc1_unblocked_ok
                {'number': '+911234567892', 'wa_account_id': cls.whatsapp_account.id, 'active': False},    # acc1_unblocked_fail
                {'number': '+911234567893', 'wa_account_id': cls.whatsapp_account.id},                     # acc1_blocked_ok
                {'number': '+911234567894', 'wa_account_id': cls.whatsapp_account.id},                     # acc1_blocked_fail
                {'number': '+911234567895', 'wa_account_id': cls.whatsapp_account.id, 'active': False},    # acc1_unblocked_neither
                {'number': '+911234567896', 'wa_account_id': cls.whatsapp_account.id},                     # acc1_blocked_neither
                {'number': '+911234567891', 'wa_account_id': cls.whatsapp_account_2.id, 'active': False},  # acc2_unblocked_ok
                {'number': '+911234567892', 'wa_account_id': cls.whatsapp_account_2.id, 'active': False},  # acc2_unblocked_fail
                {'number': '+911234567893', 'wa_account_id': cls.whatsapp_account_2.id},                   # acc2_blocked_ok
                {'number': '+911234567894', 'wa_account_id': cls.whatsapp_account_2.id},                   # acc2_blocked_fail
                {'number': '+911234567895', 'wa_account_id': cls.whatsapp_account_2.id, 'active': False},  # acc2_unblocked_neither
                {'number': '+911234567896', 'wa_account_id': cls.whatsapp_account_2.id},                   # acc2_blocked_neither
            ])


@tagged('wa_blocklist')
class WhatsAppBlocklist(WhatsAppBlocklistCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.block_status_result = {
            'failed_numbers': ('+911234567892', '+911234567894', '+911234567898'),
            'ignored_numbers': ('+911234567895', '+911234567896', '+911234567890'),
        }

    @users('user_wa_admin')
    def test_whatsapp_blocklist_block_number(self):
        """ Check whatsapp.blocklist block behavior """
        for block_record, expected_active in [
            (self.acc1_unblocked_ok, True),
            (self.acc1_unblocked_fail, False),  # fails at WA call
        ]:
            with self.subTest(record=block_record.number), self.mockWhatsappGateway(block_status_result=self.block_status_result):
                block_record.button_block_number()
                self.assertEqual(block_record.active, expected_active)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_block_on_create(self):
        for number, expected_active in [
            ('+911234567897', True),
            ('+911234567898', False),  # Failed to block
            ('+911234567890', False),  # Neither in failed nor in updated
        ]:
            with self.subTest(number=number, expected_active=expected_active), self.mockWhatsappGateway(block_status_result=self.block_status_result):
                record = self.env['whatsapp.blocklist'].create({
                    'number': number,
                    'wa_account_id': self.whatsapp_account.id,
                })
                self.assertEqual(record.active, expected_active)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_block_on_unarchive(self):
        with self.mockWhatsappGateway(block_status_result=self.block_status_result):
            self.all_blocklist_records.action_unarchive()

        expected_blocked = (
            # successfully blocked
            self.acc1_unblocked_ok | self.acc2_unblocked_ok |
            # already blocked (not processed by action)
            self.acc1_blocked_ok | self.acc1_blocked_fail | self.acc1_blocked_neither |
            self.acc2_blocked_ok | self.acc2_blocked_fail | self.acc2_blocked_neither
        )
        expected_unblocked = self.all_blocklist_records - expected_blocked
        for record in expected_blocked:
            with self.subTest(record=record.number):
                self.assertTrue(record.active)
        for record in expected_unblocked:
            with self.subTest(record=record.number):
                self.assertFalse(record.active)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_create_existing_records(self):
        """Existing records are reused, archived records are reactivated unless
        active=False is requested, duplicate values are ignored and new records are
        created in the requested order.
        """
        with self.mockWhatsappGateway(block_status_result=self.block_status_result):
            wa_account_id = self.whatsapp_account.id
            records = self.env['whatsapp.blocklist'].create([
                {'number': self.acc1_blocked_ok.number, 'wa_account_id': wa_account_id},                       # Existing active -> reused
                {'number': self.acc1_unblocked_ok.number, 'wa_account_id': wa_account_id},                     # Existing archived -> reactivated
                {'number': self.acc1_unblocked_fail.number, 'wa_account_id': wa_account_id, 'active': False},  # Existing archived -> stays archived
                {'number': '+911234567899', 'wa_account_id': wa_account_id},                                   # New -> created
                {'number': '+911234567899', 'wa_account_id': wa_account_id},                                   # Duplicate -> ignored
            ])

        # Duplicate is ignored.
        self.assertEqual(len(records), 4)

        # Returned order matches the request.
        self.assertEqual(records[0], self.acc1_blocked_ok)
        self.assertEqual(records[1], self.acc1_unblocked_ok)
        self.assertEqual(records[2], self.acc1_unblocked_fail)
        self.assertEqual(records[3].number, '+911234567899')

        # Existing active record remains active.
        self.assertTrue(self.acc1_blocked_ok.active)

        # Archived record is reactivated.
        self.assertTrue(self.acc1_unblocked_ok.active)

        # Explicitly inactive record remains archived.
        self.assertFalse(self.acc1_unblocked_fail.active)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_format_number_on_create(self):
        for number, should_fail, expected_number in [
            ('123', True, None),
            ('1234567897', False, '+911234567897'),
            ('+911234567899', False, '+911234567899'),
        ]:
            with self.subTest(number=number, should_fail=should_fail), self.mockWhatsappGateway(block_status_result=self.block_status_result):
                if should_fail:
                    with self.assertRaises(exceptions.UserError):
                        self.env['whatsapp.blocklist'].create({
                            'number': number,
                            'wa_account_id': self.whatsapp_account.id,
                        })
                else:
                    rec = self.env['whatsapp.blocklist'].create({
                        'number': number,
                        'wa_account_id': self.whatsapp_account.id,
                    })
                    self.assertEqual(rec.number, expected_number)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_format_number_on_write(self):
        acc1_unblocked_ok = self.acc1_unblocked_ok.with_user(self.env.user)
        for number, should_fail, expected_number in [
            ('123', True, None),
            ('1234567897', False, '+911234567897'),
            ('+911234567899', False, '+911234567899'),
        ]:
            with self.subTest(number=number, should_fail=should_fail), self.mockWhatsappGateway(block_status_result=self.block_status_result):
                if should_fail:
                    with self.assertRaises(exceptions.UserError):
                        acc1_unblocked_ok.number = number
                else:
                    acc1_unblocked_ok.number = number
                    self.assertEqual(acc1_unblocked_ok.number, expected_number)

    def test_whatsapp_blocklist_search_normalizes_number(self):
        blocklist = self.env['whatsapp.blocklist']
        with self.mockWhatsappGateway(block_status_result=self.block_status_result):
            bl_entry = blocklist.create({'number': '+911234567897', 'wa_account_id': self.whatsapp_account.id})
        # be sure there is no company fallback for this test
        self.env.company.country_id = False

        for user_country in [
            self.env.ref('base.be'),  # other country (should work as complete number)
            self.env.ref('base.in'),  # correct country
            self.env['res.country'],  # no country
        ]:
            with self.subTest(country_name=user_country.name or 'No country'):
                self.env.user.country_id = user_country

                res = blocklist.search([('number', 'in', ['+911 2345 67897'])])
                self.assertEqual(res, bl_entry)

                res = blocklist.search([('number', '=', '+911 2345 67897')])
                self.assertEqual(res, bl_entry)

                res = blocklist.search([('number', '=', '+911234567897')])
                self.assertEqual(res, bl_entry)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_unblock_number(self):
        for record, expected_active in [
            (self.acc1_blocked_ok, False),
            (self.acc1_blocked_fail, True),
        ]:
            with self.subTest(record=record.number), self.mockWhatsappGateway(block_status_result=self.block_status_result):
                record.button_unblock_number()
                self.assertEqual(record.active, expected_active)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_unblock_on_archive(self):
        with self.mockWhatsappGateway(block_status_result=self.block_status_result):
            self.all_blocklist_records.action_archive()

        expected_unblocked = (
            # successfully unblocked
            self.acc1_blocked_ok | self.acc2_blocked_ok |
            # already unblocked (not processed by action)
            self.acc1_unblocked_ok | self.acc1_unblocked_fail | self.acc1_unblocked_neither |
            self.acc2_unblocked_ok | self.acc2_unblocked_fail | self.acc2_unblocked_neither
        )
        expected_blocked = self.all_blocklist_records - expected_unblocked
        for record in expected_unblocked:
            with self.subTest(record=record.number):
                self.assertFalse(record.active)
        for record in expected_blocked:
            with self.subTest(record=record.number):
                self.assertTrue(record.active)

    @users('user_wa_admin')
    def test_whatsapp_blocklist_unlink(self):
        with self.mockWhatsappGateway(block_status_result=self.block_status_result):
            self.all_blocklist_records.unlink()

        # Ensure records are deleted even if unblock fails.
        for record in self.all_blocklist_records:
            with self.subTest():
                self.assertFalse(record.exists())
