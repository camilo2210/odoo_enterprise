# Part of Odoo. See LICENSE file for full copyright and licensing details.

from copy import deepcopy
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time

from odoo import tests
from odoo.addons.mail.tests.common import MailCase, mail_new_test_user
from odoo.exceptions import UserError
from odoo.tests import Form, users
from odoo.tests.common import new_test_user
from odoo.tools.misc import format_date


@tests.tagged('post_install', '-at_install')
class TestRuleParameter(MailCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rule_parameter = cls.env['hr.rule.parameter'].create({
            'name': 'Test Parameter',
            'code': 'test_param',
        })

        cls.user_payroll_manager = mail_new_test_user(
            cls.env,
            groups='base.group_user,base.group_partner_manager,hr.group_hr_manager,hr_payroll.group_hr_payroll_manager',
            login='user_payroll_manager',
            name='Urusla Udidgood',
        )

        values = []
        for year in [2016, 2017, 2018, 2020]:
            values.append({
                'rule_parameter_id': cls.rule_parameter.id,
                'parameter_value': str(year),
                'date_from': date(year, 1, 1)
            })
        cls.rule_values = cls.env['hr.rule.parameter.value'].create(values)

    @freeze_time(datetime(2019, 10, 10))
    def test_get_last_version(self):
        value = self.env['hr.rule.parameter']._get_parameter_from_code('test_param')
        self.assertEqual(value, 2018, "It should get last valid value")

    def test_get_middle_version(self):
        value = self.env['hr.rule.parameter']._get_parameter_from_code('test_param', date=date(2017, 5, 5))
        self.assertEqual(value, 2017, "It should get the 2017 version")

    def test_get_unexisting_version(self):
        with self.assertRaises(UserError):
            value = self.env['hr.rule.parameter']._get_parameter_from_code('test_param', date=date(2014, 5, 5))

    def test_wrong_code(self):
        with self.assertRaises(UserError):
            value = self.env['hr.rule.parameter']._get_parameter_from_code('wrong_code')

    def test_multicompany(self):
        """ Test value is not reused from cache when allowed_company_ids changes """

        be = self.env.ref('base.be')
        fr = self.env.ref('base.fr')
        company_1 = self.env['res.company'].create({'name': 'Table', 'country_id': be.id})
        company_2 = self.env['res.company'].create({'name': 'Tableau', 'country_id': fr.id})
        user = new_test_user(self.env, login='bub', groups='hr.group_hr_user',
                             company_id=company_2.id,
                             company_ids=[(6, 0, (company_1 + company_2).ids)])

        rule_parameter = self.env['hr.rule.parameter'].create({
            'name': 'Test Parameter',
            'code': 'test_parameter',
            'country_id': be.id,
        })
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': rule_parameter.id,
            'date_from': date(2015, 10, 10),
            'parameter_value': 100,
        })

        with self.assertRaisesRegex(UserError, "No rule parameter with code .* found"):
            # Read a BE parameter from FR company
            self.env['hr.rule.parameter'].with_user(user).with_context(allowed_company_ids=[company_2.id])._get_parameter_from_code('test_parameter')

        # Read a BE parameter from BE company, value is set in cache
        be_value = self.env['hr.rule.parameter'].with_user(user).with_context(allowed_company_ids=[company_1.id])._get_parameter_from_code('test_parameter')
        self.assertEqual(be_value, 100)

        with self.assertRaises(UserError):
            # Read a BE parameter from FR company
            # Value should not come from cache, access rights should be checked
            self.env['hr.rule.parameter'].with_user(user).with_context(allowed_company_ids=[company_2.id])._get_parameter_from_code('test_parameter')

    def test_future_rule_parameter(self):
        """Test rule parameter value creation with future date"""
        with Form(self.env['hr.rule.parameter']) as rule:
            rule.name = 'Test Future Parameter'
            rule.code = 'test_future_param'
            with rule.parameter_version_ids.new() as rule_value:
                rule_value.parameter_value = '2'
                rule_value.date_from = date.today() + relativedelta(months=2)
        new_rule = rule.save()
        self.assertTrue(new_rule.exists())

    @users('user_payroll_manager')
    def test_value_tracking(self):
        """ Test tracking of parameter value which are logged on parent parameter """
        self.env = self.env(context={**self.env.context, 'lang': 'en_US'})
        rule_parameter = self.rule_parameter.with_env(self.env)
        values = []
        for year in [2021, 2022, 2023]:
            values.append({
                'rule_parameter_id': rule_parameter.id,
                'parameter_value': str(year),
                'date_from': date(year, 1, 1)
            })
        # test tracking at create
        with self.mock_mail_gateway(), self.mock_mail_app():
            rule_values = self.env['hr.rule.parameter.value'].create(values)
            self.flush_tracking()
        expected_trackings_all = [
            [('parameter_value', 'text', False, '2021', {'html_string': 'Parameter Value'})],
            [('parameter_value', 'text', False, '2022', {'html_string': 'Parameter Value'})],
            [('parameter_value', 'text', False, '2023', {'html_string': 'Parameter Value'})],
        ]  # loop on records, parameter_value always before date_from
        for message, rule_value, expected_trackings in zip(self._new_msgs, rule_values, expected_trackings_all, strict=True):
            self.assertMessageFields(message, {
                'author_id': self.user_payroll_manager.partner_id,
                'body': f'<span class="fw-bold">Creating value for {format_date(rule_value.env, rule_value.date_from)}.</span>',
                'message_type': 'tracking',
                'model': rule_parameter._name,
                'res_id': rule_parameter.id,
                'subtype_id': self.env.ref('mail.mt_note'),
                'subject': False,
                'tracking_values': expected_trackings,
            })
        self.assertEqual(len(self.rule_parameter.message_ids), 4, 'Creation message + 3 tracking messages')

        # test tracking at write
        previous_dates_from = rule_values.mapped('date_from')
        with self.mock_mail_gateway(), self.mock_mail_app():
            for ctr, rule in enumerate(rule_values):
                rule.write({
                    'date_from': date(2026, 1, 1) + timedelta(days=ctr),
                    'parameter_value': '4098',
                })
            self.flush_tracking()
        self.assertEqual(len(self._new_msgs), 3, 'One tracking message / record')
        expected_trackings_all = [
            [
                ('parameter_value', 'text', '2021', '4098', {'html_string': 'Parameter Value'}),
                ('date_from', 'date', datetime(2021, 1, 1), datetime(2026, 1, 1), {'html_string': 'From'}),
            ], [
                ('parameter_value', 'text', '2022', '4098', {'html_string': 'Parameter Value'}),
                ('date_from', 'date', datetime(2022, 1, 1), datetime(2026, 1, 2), {'html_string': 'From'}),
            ], [
                ('parameter_value', 'text', '2023', '4098', {'html_string': 'Parameter Value'}),
                ('date_from', 'date', datetime(2023, 1, 1), datetime(2026, 1, 3), {'html_string': 'From'}),
            ],
        ]  # loop on records, parameter_value always before date_from
        for message, previous_date_from, expected_trackings in zip(self._new_msgs, previous_dates_from, expected_trackings_all, strict=True):
            self.assertMessageFields(message, {
                'author_id': self.user_payroll_manager.partner_id,
                'body': f'<span class="fw-bold">Modifying value for {format_date(rule_value.env, previous_date_from)}.</span>',
                'message_type': 'tracking',
                'model': rule_parameter._name,
                'res_id': rule_parameter.id,
                'subtype_id': self.env.ref('mail.mt_note'),
                'subject': False,
                'tracking_values': expected_trackings,
            })

    def test_rule_parameter_modified_cache(self):
        """
        Rule parameters are cached using @ormcache, functions using @ormcache
        are not supposed to return mutable data (but rule params can be mutable)

        This function tests whether _get_parameter_from_code() handles the issue
        correctly (the issue being that cached mutable data's changes are
        reflected for any subsequent calls)
        """
        rule_parameter = self.env['hr.rule.parameter'].create({
            'name': 'Mutable Rule Parameter',
            'code': 'mutable_rule_parameter',
        })
        mutable_data = [5, 0, 3]
        self.env['hr.rule.parameter.value'].create({
            'rule_parameter_id': rule_parameter.id,
            'date_from': date(2015, 10, 10),
            'parameter_value': deepcopy(mutable_data),
        })
        value = self.env['hr.rule.parameter']._get_parameter_from_code('mutable_rule_parameter')
        self.assertEqual(
            mutable_data, value, "Expected to get assigned parameter_value when calling _get_parameter_from_code()",
        )
        value.append(10)  # this should not affect subsequent calls to _get_parameter_from_code()
        value = self.env['hr.rule.parameter']._get_parameter_from_code('mutable_rule_parameter')
        self.assertEqual(
            mutable_data, value, """
_get_parameter_from_code() should always return the defined parameter_value,
even if the return value has been modified by a caller at some point.
This issue usually occurs when modifying cached mutable data.
            """,
        )
