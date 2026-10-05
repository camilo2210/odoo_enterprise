# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging
from datetime import date, datetime

from odoo.fields import Command, Date
from odoo.tools import config, file_open, file_path, float_compare

from odoo.tests.common import TransactionCase, new_test_user
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

# Placeholder stored in the JSON snapshots instead of volatile values (record ids, dates...)
SNAPSHOT_IGNORE = '___ignore___'


class TestPayrollBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids += cls.env.ref('hr_payroll.group_hr_payroll_user')

    @classmethod
    def _setup_common(cls, country, structure, structure_type, resource_calendar=False, car=False, version_fields=False, employee_fields=False, version_properties=False, tz=False):
        """
        This method setups a set of common models that will be used to test payslip validation.

        It will create a partner and an employee that are in the company in cls.env.company.
        The employee and company resource calendar will be a standard full-time 40h/week calendar.
        The default timezone is 'America/Los_Angeles'.

        It will also create a contract for the employee in the same company with:
            - a default start date at the 1st of January 2016
            - a default wage amounting to 1000.0 of whatever the currency of the company is.

        In the following parameter descriptions, 'xx' is the standard 2-letter country code.
        :param country: Record of the country (usually base.xx)
        :param structure: Record of the default structure (usually l10n_xx_hr_payroll.hr_payroll_structure_xx_employee_salary)
        :param structure_type: Record of the default structure type (usually l10n_xx_hr_payroll.structure_type_employee_xx)
        :param resource_calendar: Record of a resource calendar if you want to replace the default one
        :param car: Record of the employee's fleet car, False by default
        :param version_fields: Dict of field names: value, that will be overridden on the contract created
        :param employee_fields: Dict of field names: value, that will be overridden on the employee created
        :param tz: String of a timezone that is set for both the user and the resource calendar
        :return:
        """
        cls.country = country
        country_code = country.code.upper()

        cls.structure = structure

        cls.tz = tz or 'America/Los_Angeles'
        cls.env.user.tz = cls.tz

        cls.work_contact = cls.env['res.partner'].create({
            'name': country_code + ' Employee',
            'company_id': cls.env.company.id,
        })
        work_entry_type = cls.env['hr.work.entry.type'].sudo().search([
            ('country_id', '=', country.id),
            ('code', '=', '002.00'),
        ], limit=1) or cls.env.ref('hr_work_entry.generic_work_entry_type_attendance')
        cls.env.company.country_id = country
        cls.resource_calendar = resource_calendar or cls.env['resource.calendar'].sudo().create([{
            'name': "Standard Calendar : 40 Hours/Week",
            'company_id': cls.env.company.id,
            'hours_per_day': 8.0,
            'hours_per_week': 40.0,
            'full_time_required_hours': 40.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': work_entry_type.id,
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 17.0),
                ("1", 8.0, 12.0),
                ("1", 13.0, 17.0),
                ("2", 8.0, 12.0),
                ("2", 13.0, 17.0),
                ("3", 8.0, 12.0),
                ("3", 13.0, 17.0),
                ("4", 8.0, 12.0),
                ("4", 13.0, 17.0),
            ]],
        }]).sudo(False)
        cls.env.company.write({
            'resource_calendar_id': cls.resource_calendar.id,
            'country_id': country.id,
        })
        cls.resource_calendar.reference_calendar_id = cls.resource_calendar

        cls.employee = cls.env['hr.employee'].sudo().create({
            'name': country_code + ' Employee',
            'work_contact_id': cls.work_contact.id,
            'address_id': cls.work_contact.id,
            'resource_calendar_id': cls.resource_calendar.id,
            'company_id': cls.env.company.id,
            'country_id': country.id,
            'structure_type_id': structure_type.id,
            'contract_date_start': date(2016, 1, 1),
            'date_version': date(2016, 1, 1),
            'wage': 1000.0,
            **(employee_fields or {})
        }).sudo(False)

        version = cls.employee.sudo().version_id
        if version_fields:
            version.write(version_fields)
        for code, value in (version_properties or {}).items():
            version._set_property_input_value(code, value)
        cls.version = version.sudo(False)

        cls.car = car
        if cls.car:
            cls.car.sudo().write({'driver_id': cls.employee.work_contact_id.id})
            # This field only exists if fleet is installed
            cls.version.sudo().write({'car_id': cls.car.id})

    @classmethod
    def _generate_payslip(cls, date_from, date_to, struct_id=False, input_line_ids=False, version_id=False, employee_id=False):
        vals = {
            'name': "Test Payslip",
            'employee_id': employee_id or cls.employee.id,
            'version_id': version_id or cls.version.id,
            'company_id': cls.env.company.id,
            'struct_id': struct_id or cls.structure.id,
            'date_from': date_from,
            'date_to': date_to,
        }
        if input_line_ids:
            vals['input_line_ids'] = input_line_ids
        payslip = cls.env['hr.payslip'].create([vals])
        # This field only exists if fleet is installed
        if cls.car:
            payslip.write({'vehicle_id': cls.car.id})
        payslip.compute_sheet()
        return payslip

    @classmethod
    def _generate_leave(cls, employee, date_from, date_to, work_entry_type_id, create_allocation=True):
        if isinstance(date_from, str):
            date_from = date.fromisoformat(date_from)
        if isinstance(date_to, str):
            date_to = date.fromisoformat(date_to)

        if work_entry_type_id.requires_allocation and create_allocation:
            allocation = cls.env['hr.leave.allocation'].sudo().create({
                'date_from': date_from,
                'date_to': date_to,
                'number_of_days': (date_to - date_from).days + 1,
                'work_entry_type_id': work_entry_type_id.id,
                'employee_id': employee.id,
            })
            allocation.action_approve()

        leave = cls.env['hr.leave'].sudo().create({
            'employee_id': employee.id,
            'request_date_from': date_from,
            'request_date_to': date_to,
            'work_entry_type_id': work_entry_type_id.id,
        })

        if work_entry_type_id.leave_validation_type != 'no_validation':
            leave.action_approve()

    def _add_other_input(self, payslip_id, other_input_id, amount):
        self.env['hr.payslip.input'].create({
            'payslip_id': payslip_id.id,
            'salary_rule_id': other_input_id.id,
            'amount': amount,
        })

    def _add_rule_parameter_value(self, rule_parameter_code, value, date):
        rule_parameter_id = self.env['hr.rule.parameter'].search([('code', '=', rule_parameter_code)]).id
        value_on_same_date = self.env['hr.rule.parameter.value'].search([
            ('rule_parameter_id', '=', rule_parameter_id),
            ('date_from', '=', date)
        ])
        if value_on_same_date:
            value_on_same_date.sudo().write({'parameter_value': value})
        else:
            self.env['hr.rule.parameter.value'].sudo().create({
                'rule_parameter_id': rule_parameter_id,
                'parameter_value': value,
                'date_from': date,
            })

    def _get_payslip_property_amount(self, payslip, code):
        """Return the amount of a property-input row on the payslip for the rule with the given code."""
        line = payslip.input_line_ids.filtered(lambda l: l.code == code)
        return line[:1].amount if line else 0

    def _validate_rule_computed(self, payslip, rule_code, expected=True):
        rule_computed = bool(payslip.line_ids.filtered(lambda l: l.code == rule_code))
        self.assertEqual(rule_computed, expected, f'Rule {rule_code} should {'' if expected else 'not '}be computed')

    # ------------------------------------------------------------------
    # JSON snapshots
    # ------------------------------------------------------------------
    # Expected values can be stored in JSON files instead of being inlined in
    # the test, one file per test method and one key per line, payslip lines in
    # the order of the payslip (salary rule sequence):
    #   <module>/tests/test_files/<kind>/<test file>/<test method>.json
    # To (re)generate them, append a pseudo tag to the --test-tags selector
    # (same convention as AccountTestInvoicingCommon.assert_json):
    #   ,SAVE_JSON          rewrite the snapshots reached by the selected tests
    #   ,SAVE_JSON_ON_FAIL  rewrite only the snapshots that don't match anymore
    # e.g. --test-tags=/test_l10n_be_hr_payroll_account:TestPayslipValidation.test_low_salary,SAVE_JSON
    # These tags select no test by themselves: always combine them with a real
    # selector, then review the JSON diff before committing it.
    # The files are read and written with file_open(), which never creates
    # files: a new snapshot must exist as an empty file before SAVE_JSON can
    # fill it.
    # On a merge/rebase conflict on snapshot files, keep either side and re-run
    # the tests with SAVE_JSON_ON_FAIL: the files are regenerated from the code.

    @staticmethod
    def _snapshot_mode():
        tags = {tag.strip().lstrip('+') for tag in (config['test_tags'] or '').split(',')}
        if 'SAVE_JSON' in tags:
            return 'save'
        if 'SAVE_JSON_ON_FAIL' in tags:
            return 'save_on_fail'
        return 'assert'

    def _snapshot_path(self, kind):
        test_file = self.__class__.__module__.rsplit('.', 1)[-1]
        return file_path(
            f"{self.test_module}/tests/test_files/{kind}/{test_file}/{self._testMethodName}.json",
            check_exists=False,
        )

    def _snapshot_label(self, label, prefix):
        # one counter per test method: unittest instantiates the class per test
        counters = self.__dict__.setdefault('_snapshot_counters', {})
        counters[prefix] = counters.get(prefix, 0) + 1
        return label or f"{prefix}_{counters[prefix]}"

    @staticmethod
    def _snapshot_load(path):
        """Return the content of the snapshot file, {} when empty, None when missing."""
        try:
            with file_open(path) as snapshot_file:
                content = snapshot_file.read()
        except FileNotFoundError:
            return None
        return json.loads(content) if content.strip() else {}

    @staticmethod
    def _snapshot_missing_message(path, label, file_exists):
        message = f"Snapshot {path} [{label}] not found: "
        if not file_exists:
            message += "create it as an empty file (and its folder), then "
        return message + "run this test with ',SAVE_JSON' appended to --test-tags to fill it."

    def _snapshot_store(self, path, label, content, sort_keys=True):
        pending = self.__dict__.setdefault('_snapshot_pending', {})
        if path not in pending:
            # SAVE_JSON rebuilds the file from scratch so that the labels of
            # removed assertions don't linger
            pending[path] = {} if self._snapshot_mode() == 'save' else (self._snapshot_load(path) or {})
        pending[path][label] = content
        try:
            with file_open(path, 'w') as snapshot_file:
                json.dump(pending[path], snapshot_file, indent=4, sort_keys=sort_keys)
                snapshot_file.write('\n')
        except FileNotFoundError:
            saved = False
        else:
            saved = True
        if not saved:
            # file_open() refuses to create files
            self.fail(self._snapshot_missing_message(path, label, file_exists=False))
        _logger.info("Saved snapshot %s [%s]", path, label)
        return content

    @classmethod
    def _snapshot_mask(cls, data, ignore_keys):
        if isinstance(data, dict):
            return {
                key: SNAPSHOT_IGNORE if key in ignore_keys else cls._snapshot_mask(value, ignore_keys)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [cls._snapshot_mask(value, ignore_keys) for value in data]
        return data

    def _assert_dict_snapshot(self, actual, kind, label=None, ignore_keys=(), diff=None):
        """Compare a JSON-serializable dict/list with the snapshot of the test.

        :param kind: sub-folder of tests/test_files, e.g. 'dmfa'
        :param label: key in the snapshot file, defaults to '<kind>_1', '<kind>_2', ...
            following the order of the calls in the test
        :param ignore_keys: keys holding volatile values (record ids, dates...),
            masked recursively before comparing and saving
        :param diff: optional callable(actual, expected) -> str, empty when equal,
            used to build a readable assertion message
        """
        actual = self._snapshot_mask(json.loads(json.dumps(actual)), ignore_keys)
        path = self._snapshot_path(kind)
        label = self._snapshot_label(label, kind)
        mode = self._snapshot_mode()
        if mode == 'save':
            return self._snapshot_store(path, label, actual)
        data = self._snapshot_load(path)
        expected = (data or {}).get(label)
        if expected is None:
            if mode == 'save_on_fail':
                return self._snapshot_store(path, label, actual)
            self.fail(self._snapshot_missing_message(path, label, file_exists=data is not None))
        expected = self._snapshot_mask(expected, ignore_keys)
        if expected == actual:
            return
        if mode == 'save_on_fail':
            return self._snapshot_store(path, label, actual)
        hint = f"Snapshot {path} [{label}]: re-run this test with ',SAVE_JSON_ON_FAIL' appended to --test-tags to refresh it, then review the JSON diff."
        if diff:
            self.fail(f"{diff(actual, expected)}\n\n{hint}")
        self.assertEqual(actual, expected, hint)

    def _validate_payslip(self, payslip, results=None, skip_lines=False, label=None):
        """Check the totals of the payslip lines.

        :param results: {rule code: expected total}. When omitted, the expected
            values come from the JSON snapshot of the test
            (tests/test_files/payslips/<test file>/<test method>.json, see above)
        :param skip_lines: don't fail on payslip lines absent from `results`, for
            targeted assertions on a few rules (not available in snapshot mode)
        :param label: key in the snapshot file, defaults to 'payslip_1',
            'payslip_2', ... following the order of the calls in the test
        :return: the expected values, e.g. to cross-check totals between payslips
        """
        payslip_lines = payslip.line_ids.filtered(lambda l: not l.salary_rule_id.title)
        line_values = payslip._get_line_values(set(payslip_lines.mapped('code')))
        # raw totals: 3-decimal currencies (IQD, OMR, ...) expect 3-decimal values,
        # float_compare() below rounds both sides consistently
        actual = {
            line.code: line_values[line.code][payslip.id]['total'] or 0.0
            for line in payslip_lines
        }
        snapshot = None
        if results is None:
            assert not skip_lines, "A snapshot always contains every line: skip_lines is meaningless"
            snapshot = (self._snapshot_path('payslips'), self._snapshot_label(label, 'payslip'))
            mode = self._snapshot_mode()
            if mode == 'save':
                return self._snapshot_store(*snapshot, actual, sort_keys=False)
            data = self._snapshot_load(snapshot[0])
            results = (data or {}).get(snapshot[1])
            if results is None:
                if mode == 'save_on_fail':
                    return self._snapshot_store(*snapshot, actual, sort_keys=False)
                self.fail(self._snapshot_missing_message(*snapshot, file_exists=data is not None))
        error = []
        for code, value in results.items():
            if code not in actual:
                error.append(f"{'RULE NOT COMPUTED':>20} │ {code:<30} │ {value:>15} │ {'/':>15} │")
            elif float_compare(actual[code], value, 2):
                error.append(f"{'WRONG CALCULATION':>20} │ {code:<30} │ {value:>15} │ {actual[code]:>15} │ {round(actual[code] - value, 2):>15} │")
        if not skip_lines:
            for code, value in actual.items():
                if code not in results:
                    error.append(f"{'MISSING LINE':>20} │ {code:<30} │ {'/':>15} │ {value:>15} │")
        if error:
            if snapshot and self._snapshot_mode() == 'save_on_fail':
                return self._snapshot_store(*snapshot, actual, sort_keys=False)
            error.insert(
                0,
                f"{'ERROR':>20} │ {'CODE':<30} │ {'EXPECTED':>15} │ {'REALITY':>15} │ {'DIFFERENCE':>15} │\n"
                f"{'':>20} │ {'':<30} │ {'':>15} │ {'':>15} │ {'':>15} │")
            error.extend(["", f"Payslip Period: {payslip.date_from} - {payslip.date_to}"])
            if snapshot:
                error.append(f"Snapshot {snapshot[0]} [{snapshot[1]}]: re-run this test with ',SAVE_JSON_ON_FAIL' appended to --test-tags to refresh it, then review the JSON diff.")
            else:
                error.append("Payslip Actual Values: ")
                error.append("        payslip_results = {")
                error.extend(f"            '{code}': {value}," for code, value in actual.items())
                error.append("        }")
        self.assertEqual(len(error), 0, '\n\n' + '\n'.join(error))
        return results

    def _validate_worked_days(self, payslip, results, skip_lines=False):
        error = []
        line_values = payslip._get_worked_days_line_values(set(results.keys()) | set(payslip.worked_days_line_ids.mapped('code')), ['number_of_days', 'number_of_hours', 'amount'])
        for code, (number_of_days, number_of_hours, amount) in results.items():
            payslip_line_value = line_values[code][payslip.id]['number_of_days']
            if float_compare(payslip_line_value, number_of_days, 2):
                error.append("Code: %s - Expected Number of Days: %s - Reality: %s" % (code, number_of_days, payslip_line_value))
            payslip_line_value = line_values[code][payslip.id]['number_of_hours']
            if float_compare(payslip_line_value, number_of_hours, 2):
                error.append("Code: %s - Expected Number of Hours: %s - Reality: %s" % (code, number_of_hours, payslip_line_value))
            payslip_line_value = line_values[code][payslip.id]['amount']
            if float_compare(payslip_line_value, amount, 2):
                error.append("Code: %s - Expected Amount: %s - Reality: %s" % (code, amount, payslip_line_value))
        if not skip_lines:
            for line in payslip.worked_days_line_ids:
                if line.code not in results:
                    error.append("Missing Line: '%s' - %s Days - %s Hours - %s," % (
                        line.code,
                        line_values[line.code][payslip.id]['number_of_days'],
                        line_values[line.code][payslip.id]['number_of_hours'],
                        line_values[line.code][payslip.id]['amount'],
                    ))
        if error:
            error.extend([
                f"Payslip Period: {payslip.date_from} - {payslip.date_to}",
                "Payslip Actual Values: ",
                "        {"
            ])
            for line in payslip.worked_days_line_ids:
                error.append("            '%s': (%s, %s, %s)," % (
                    line.code,
                    line_values[line.code][payslip.id]['number_of_days'],
                    line_values[line.code][payslip.id]['number_of_hours'],
                    line_values[line.code][payslip.id]['amount'],
                ))
            error.append("        }")
        self.assertEqual(len(error), 0, '\n' + '\n'.join(error))


class TestPayslipBase(TestPayrollBase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        payroll_manager = cls.env.ref('hr_payroll.group_hr_payroll_manager')
        cls.env.user.group_ids |= payroll_manager
        cls.company_us = cls.env['res.company'].create({
            'name': 'Company US',
            'country_id': cls.env.ref('base.us').id,
        })

        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company_us.ids))
        cls.env.company.tz = 'Europe/Brussels'
        cls.env.user.tz = 'Europe/Brussels'

        cls.dep_rd = cls.env['hr.department'].sudo().create({
            'name': 'Research & Development - Test',
        }).sudo(False)

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer',
        })

        cls.richard_emp = cls.env['hr.employee'].create({
            'name': 'Richard',
            'sex': 'male',
            'birthday': '1984-05-01',
            'country_id': cls.env.ref('base.us').id,
            'department_id': cls.dep_rd.id,
            'date_version': Date.to_date('2018-01-01'),
            'contract_date_start': Date.to_date('2018-01-01'),
            'contract_date_end': Date.today() + relativedelta(years=2),
            'wage': 5000.33,
            'structure_type_id': cls.structure_type.id,
        })

        cls.jules_emp = cls.env['hr.employee'].create({
            'name': 'Jules',
            'sex': 'male',
            'birthday': '1984-05-01',
            'country_id': cls.env.ref('base.us').id,
            'department_id': cls.dep_rd.id,
        })

        cls.richard_bank_acc = cls.env['res.partner.bank'].create({
            'account_number': 'BE00111122223333',
            "partner_id": cls.richard_emp.work_contact_id.id,
            "allow_out_payment": True
        })
        cls.richard_emp.bank_account_ids = [Command.link(cls.richard_bank_acc.id)]

        cls.richard_contract = cls.richard_emp.version_id

        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Extra attendance',
            'count_as': 'working_time',
            'code': 'WORKTEST200',
            'requires_allocation': False,
            'request_unit': 'hour',
        })

        cls.work_entry_type_unpaid = cls.env['hr.work.entry.type'].create({
            'name': 'Unpaid Leave',
            'count_as': 'absence',
            'code': 'LEAVETEST300',
            'amount_rate': 0.0,
            'request_unit': 'half_day',
            'round_days_type': 'DOWN',
            'requires_allocation': False,
        })

        cls.work_entry_type_leave = cls.env['hr.work.entry.type'].create({
            'name': 'Leave',
            'count_as': 'absence',
            'code': 'LEAVETEST100',
            'requires_allocation': False,
        })

        # I create a work entry type with work rate
        cls.work_entry_type_overtime_duty = cls.env['hr.work.entry.type'].create({
            'name': 'Overtime Duty',
            'count_as': 'working_time',
            'code': 'WORKRATETEST400',
            'amount_rate': 0.5,
            'category_ids': [Command.link(cls.env.ref('hr_payroll.EXTRA_HOURS').id)],
            'requires_allocation': False,
            'request_unit': 'hour',
        })

        # I create a salary structure for "Software Developer"
        cls.developer_pay_structure = cls.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Software Developer',
            'type_id': cls.structure_type.id,
        })

        cls.hra_rule = cls.env['hr.salary.rule'].create({
            'name': 'House Rent Allowance',
            'sequence': 5,
            'amount_select': 'percentage',
            'amount_percentage': 40.0,
            'amount_percentage_base': 'version.wage',
            'code': 'HRA',
            'category_ids': [(4, cls.env.ref('hr_payroll.ALW').id)],
            'struct_ids': [(4, cls.developer_pay_structure.id)],
        })

        cls.conv_rule = cls.env['hr.salary.rule'].create({
            'name': 'Conveyance Allowance',
            'sequence': 10,
            'amount_select': 'fix',
            'amount_fix': 800.0,
            'code': 'CA',
            'category_ids': [(4, cls.env.ref('hr_payroll.ALW').id)],
            'struct_ids': [(4, cls.developer_pay_structure.id)],
        })

        cls.mv_rule = cls.env['hr.salary.rule'].create({
            'name': 'Meal Voucher',
            'sequence': 16,
            'amount_select': 'fix',
            'amount_fix': 10,
            'quantity': "'002.00' in worked_days and worked_days['002.00'].number_of_days",
            'code': 'MA',
            'category_ids': [(4, cls.env.ref('hr_payroll.ALW').id)],
            'struct_ids': [(4, cls.developer_pay_structure.id)],
        })

        cls.sum_of_alw = cls.env['hr.salary.rule'].create({
            'name': 'Sum of Allowance category',
            'sequence': 99,
            'amount_select': 'code',
            'amount_python_compute': "result = categories['ALW']",
            'quantity': "'002.00' in worked_days and worked_days['002.00'].number_of_days",
            'code': 'SUMALW',
            'category_ids': [(4, cls.env.ref('hr_payroll.ALW').id)],
            'struct_ids': [(4, cls.developer_pay_structure.id)],
        })

        cls.pf_rule = cls.env['hr.salary.rule'].create({
            'name': 'Provident Fund',
            'sequence': 120,
            'amount_select': 'percentage',
            'amount_percentage': -12.5,
            'amount_percentage_base': 'version.wage',
            'code': 'PF',
            'category_ids': [(4, cls.env.ref('hr_payroll.DED').id)],
            'struct_ids': [(4, cls.developer_pay_structure.id)],
        })

        cls.prof_tax_rule = cls.env['hr.salary.rule'].create({
            'name': 'Professional Tax',
            'sequence': 150,
            'amount_select': 'fix',
            'amount_fix': -200.0,
            'code': 'PT',
            'category_ids': [(4, cls.env.ref('hr_payroll.DED').id)],
            'struct_ids': [(4, cls.developer_pay_structure.id)],
        })

        # Pick up the standard adjustment / deduction rules that were copied from
        # hr_payroll.default_structure (data/hr_salary_rule_data.xml) into the new
        # developer_pay_structure. The refactor only needs to flip the new flag
        # fields and activate them for tests; the rule definitions themselves
        # (condition_python / amount_python_compute matching by code) are kept.
        def _rule_by_code(code, **flag_overrides):
            rule = cls.developer_pay_structure.rule_ids.with_context(active_test=False).filtered(lambda r: r.code == code)
            assert rule, f"Expected default_structure to seed a {code} rule"
            rule.write({'active': True, **flag_overrides})
            return rule

        cls.deduction_rule = _rule_by_code('DEDUCTION')
        cls.reimbursement_rule = _rule_by_code('REIMBURSEMENT')
        cls.attach_salary_rule = _rule_by_code('ATTACH_SALARY', input_usage_payslip=True)
        cls.assign_salary_rule = _rule_by_code('ASSIG_SALARY', input_usage_payslip=True)
        cls.child_support_rule = _rule_by_code('CHILD_SUPPORT', input_usage_payslip=True)

        cls.structure_type.default_struct_id = cls.developer_pay_structure

        cls.env.user.write({'group_ids': [
            Command.unlink(payroll_manager.id),
            Command.link(cls.env.ref('hr_payroll.group_hr_payroll_officer').id),
        ]})

    @classmethod
    def get_default_groups(cls):
        # to create res.partner.bank in setup
        return super().get_default_groups() | cls.quick_ref('base.group_partner_manager')


class TestPayslipContractBase(TestPayslipBase):

    @classmethod
    def setUpClass(cls):
        super(TestPayslipContractBase, cls).setUpClass()
        cls.calendar_richard = cls.env['resource.calendar'].create({'name': 'Calendar of Richard'})
        cls.calendar_40h = cls.env['resource.calendar'].create({'name': 'Default calendar'})
        cls.calendar_38h = cls.env['resource.calendar'].create({
            'name': 'Standard 38 hours/week',
            'company_id': False,
            'hours_per_day': 7.6,
            'attendance_ids': [(5, 0, 0),
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16.6}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16.6})
            ],
        })
        cls.calendar_35h = cls.env['resource.calendar'].create({
            'name': '35h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 16}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '4', 'hour_from': 13, 'hour_to': 16})
            ]
        })

        cls.richard_emp.resource_calendar_id = cls.calendar_richard

        cls.calendar_16h = cls.env['resource.calendar'].create({
            'name': '16h calendar',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 11.5}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 11.5}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 11.5}),
                (0, 0, {'dayofweek': '3', 'hour_from': 9, 'hour_to': 12.5}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13.5, 'hour_to': 15.5}),
            ]
        })

        cls.calendar_38h_friday_light = cls.env['resource.calendar'].create({
            'name': '38 calendar Friday light',
            'attendance_ids': [
                (0, 0, {'dayofweek': '0', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '0', 'hour_from': 13, 'hour_to': 17.5}),
                (0, 0, {'dayofweek': '1', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '1', 'hour_from': 13, 'hour_to': 17.5}),
                (0, 0, {'dayofweek': '2', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '2', 'hour_from': 13, 'hour_to': 17.5}),
                (0, 0, {'dayofweek': '3', 'hour_from': 8, 'hour_to': 12}),
                (0, 0, {'dayofweek': '3', 'hour_from': 13, 'hour_to': 17.5}),
                (0, 0, {'dayofweek': '4', 'hour_from': 8, 'hour_to': 12}),
            ]
        })

        # This contract ends at the 15th of the month
        cls.contract_cdd = cls.richard_emp.sudo().create_version({  # Fixed term contract
            'contract_date_end': datetime.strptime('2015-11-15', '%Y-%m-%d'),
            'contract_date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'date_version': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'resource_calendar_id': cls.calendar_40h.id,
            'wage': 5000.33,
            'structure_type_id': cls.structure_type.id,
        })

        # This contract starts the next day
        cls.contract_cdi = cls.richard_contract
        cls.richard_contract.sudo().write({
            'contract_date_start': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'contract_date_end': False,
            'date_version': datetime.strptime('2015-11-16', '%Y-%m-%d'),
            'resource_calendar_id': cls.calendar_35h.id,
            'wage': 5000.33,
            'structure_type_id': cls.structure_type.id,
        })

        # Contract for Jules
        cls.jules_emp.version_id.sudo().write({
            'contract_date_start': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'date_version': datetime.strptime('2015-01-01', '%Y-%m-%d'),
            'name': 'Contract for Jules',
            'resource_calendar_id': cls.calendar_40h.id,
            'wage': 5000.33,
            'employee_id': cls.jules_emp.id,
            'structure_type_id': cls.developer_pay_structure.type_id.id,
        })
        cls.contract_jules = cls.jules_emp.version_id


class TestPayrollHolidaysBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.company_id.tz = "Europe/Brussels"
        cls.env = cls.env(context={'tz': 'Europe/Brussels'})
        cls.dep_rd = cls.env['hr.department'].create({
            'name': 'Research & Development - Test',
        })

        cls.structure_type = cls.env['hr.payroll.structure.type'].create({
            'name': 'Test - Developer',
        })

        # Create employee
        cls.vlad = new_test_user(cls.env, login='vlad', groups='base.group_user,hr_holidays.group_hr_holidays_employee')
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Donald',
            'sex': 'male',
            'birthday': '1946-06-14',
            'department_id': cls.dep_rd.id,
            'user_id': cls.vlad.id,
            'date_version': Date.to_date('2018-01-01'),
            'contract_date_start': Date.to_date('2018-01-01'),
            'contract_date_end': Date.today() + relativedelta(years=2),
            'wage': 5000.0,
            'structure_type_id': cls.structure_type.id,
        })

        cls.joseph = new_test_user(cls.env, login='joseph', groups='base.group_user,hr_holidays.group_hr_holidays_user')

        cls.work_entry_type_unpaid = cls.env['hr.work.entry.type'].create({
            'name': 'Unpaid Leave',
            'count_as': 'absence',
            'code': 'LEAVETEST300',
            'amount_rate': 0.0,
            'request_unit': 'half_day',
            'round_days_type': 'DOWN',
        })

        # Create a salary structure, necessary to compute sheet
        cls.developer_pay_structure = cls.env['hr.payroll.structure'].create({
            'name': 'Salary Structure for Software Developer',
            'type_id': cls.structure_type.id,
        })
        cls.structure_type.default_struct_id = cls.developer_pay_structure

        # Create a leave type for our leaves
        cls.work_entry_type = cls.env['hr.work.entry.type'].create({
            'name': 'Unpaid leave',
            'code': 'Unpaid leave',
            'count_as': 'absence',
            'requires_allocation': False,
        })
