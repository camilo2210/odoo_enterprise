from datetime import date, datetime
from requests import Response

from odoo.addons.mail.tests.common import mail_new_test_user, MailCommon
from odoo.tests import tagged


@tagged('mail_track')
class TestCardWizards(MailCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_admin.stripe_id = 'dontknow'
        cls.user_expense_manager = mail_new_test_user(
            cls.env,
            company_id=cls.company_admin.id,
            email='exp_manager@test.example.com',
            groups='base.group_user,hr_expense.group_hr_expense_manager',
            name='Expense Manager',
            notification_type='email',
            login='exp_manager',
            tz='Europe/Brussels'
        )

        cls.test_user_employee = cls.env['hr.employee'].create({
            'private_stripe_id': 'sk_test_iNeedAtLeast16Characters',
            'user_id': cls.user_employee.id,
        })

        cls.test_card = cls.env['hr.expense.stripe.card'].create({
            'employee_id': cls.test_user_employee.id,
            'name': 'Test',
            'user_id': cls.user_employee.id,
        })

    @classmethod
    def _request_handler(cls, session, request, **kwargs):
        """ Basic mocks to make existing tests pass. Feel free to make it more
        controllable. """
        url = request.url
        if "api/stripe_issuing/v1/cardholders" in url:
            response = Response()
            response.status_code = 200
            response.json = lambda: {
                'id': 'reallydontknow',
            }
            return response
        elif "api/stripe_issuing/v1/cards" in url:
            response = Response()
            response.status_code = 200
            response.json = lambda: {
                'cancellation_reason': 'stolen',
                'exp_month': 11,
                'exp_year': 2026,
                'id': 'reallydontknow',
                'last4': 'know',
                'status': 'active',
            }
            return response
        return super()._request_handler(session, request, **kwargs)

    def test_card_holder_wizard(self):
        """ Test 'hr.expense.stripe.cardholder.wizard', more specifically tracking
        and message management. """
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        wizard = self.env['hr.expense.stripe.cardholder.wizard'].with_user(self.user_expense_manager).create({
            'billing_country_id': self.env.ref('base.be').id,  # not used in tracking (use stripe_values instead)
            'birthday': date(2102, 5, 6),  # not used in tracking (use stripe_values instead)
            'card_id': self.test_card.id,
            'company_id': self.company_admin.id,
            'email': 'not.tracked@belgium.be',  # not used in tracking (use stripe_values instead)
            'employee_id': self.test_user_employee.id,
            'phone_number': '+32455998877',  # not used in tracking (use stripe_values instead)
            'stripe_values': {  # actually tracked values
                'billing_country_id': self.env.ref('base.fr').id,
                'birthday': date(2002, 5, 6),
                'email': False,
                'phone_number': '+32455001122',
            },
        })
        self.flush_tracking()

        wizard.write({
            'billing_country_id': self.env.ref('base.be').id,
            'birthday': date(1939, 9, 1),
            'email': '"Albert, King of Belgians" <albert@belgium.be>',
            'phone_number': '+32455778899',
        })
        self.flush_tracking()

        # messages are generated at flush
        with self.mock_mail_gateway(), self.mock_mail_app():
            wizard.action_save_cardholder()
            self.flush_tracking()
        self.assertEqual(len(self._new_msgs), 1, 'Should have copied wizard traking on card')
        track_msg = self.test_card.message_ids[0]
        self.assertEqual(track_msg, self._new_msgs, 'New message logged on card')
        self.assertMessageFields(
            self._new_msgs, {
                'message_type': 'tracking',
                'tracking_values': [
                    ('billing_country_id', 'many2one', self.env.ref('base.fr'), self.env.ref('base.be'), {'html_string': 'Country'}),
                    ('birthday', 'date', datetime(2002, 5, 6, 0, 0, 0), datetime(1939, 9, 1, 0, 0, 0), {'html_string': 'Birthday'}),
                    ('email', 'char', False, '"Albert, King of Belgians" <albert@belgium.be>', {'html_string': 'Email'}),
                    ('phone_number', 'char', '+32455001122', '+32455778899', {'html_string': 'Phone Number'}),
                ],
            }
        )

    def test_card_receive_wizard(self):
        """ Test 'hr.expense.stripe.card.receive.wizard', more specifically tracking
        and message management. """
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        wizard = self.env['hr.expense.stripe.card.receive.wizard'].with_user(self.user_expense_manager).create({
            'billing_country_code': 'BE',
            'card_id': self.test_card.id,
            'is_confirmed': True,
            'original_phone_number': '+32455001122',
            'phone_number': '+32455778899',
        })
        self.flush_tracking()

        # messages are generated at flush
        with self.mock_mail_gateway(), self.mock_mail_app():
            wizard.action_receive_card()
            self.flush_tracking()

        # one posted message with manual tracking, one confirmation email send using template
        # (see '_send_delivery_emails'), then tracked fields due to card update
        self.assertEqual(len(self._new_msgs), 3)
        (track_msg_1, _notif_msg, track_msg_2) = self._new_msgs
        self.assertMessageFields(
            track_msg_1, {
                'author_id': self.user_expense_manager.partner_id,
                'body': '',
                'model': self.test_card._name,
                'res_id': self.test_card.id,
                'subject': False,
                'subtype_id': self.env.ref('hr_expense_stripe.mt_stripe_cardholder_updated'),
                'tracking_values': [
                    ('phone_number', 'char', '+32455001122', '+32455778899', {'html_string': 'Cardholder Mobile Number'}),
                ],
            }
        )
        self.assertMessageFields(
            track_msg_2, {
                'author_id': self.user_expense_manager.partner_id,
                'body': '',
                'model': self.test_card._name,
                'res_id': self.test_card.id,
                'subject': False,
                'tracking_values': [
                    ('cancellation_reason', 'selection', '', 'Stolen'),
                    ('is_delivered', 'boolean', False, True),
                    ('state', 'selection', 'Draft', 'Active'),
                ],
            }
        )
