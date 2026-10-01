# Part of Odoo. See LICENSE file for full copyright and licensing details.

import time
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.tests import freeze_time, tagged

from odoo.addons.hr_payroll_account.tests.common import TestPayslipValidationCommon
from odoo.addons.l10n_be_hr_payroll.models.certificate import CertificateCertificate
from odoo.addons.l10n_be_hr_payroll.models.utils import xml_str_to_dict
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon
from odoo.addons.l10n_be_hr_payroll.models.hr_dmfa import L10n_BeDmfa
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tools import date_utils


def get_variable_diff_as_message(actual_value, expected_value) -> str:
    """
    This function takes two values and will try to compare it (recursively if
    they are dicts/lists/tuples). If there are differences, it will return a
    description of the differences as a string, otherwise, it will return ""
    """
    # `path` represents the dict structure we are currently in
    def _diff(actual, expected, path) -> list:
        if not isinstance(actual, expected.__class__):
            return [f"{path}: type mismatch: expected {actual.__class__}, got {expected.__class__}"]

        diff_msgs_list = []
        if isinstance(expected, dict):
            all_keys = set(actual.keys()) | set(expected.keys())
            for key in sorted(all_keys):
                child_path = f"{path}[{key}]"
                if key not in actual:
                    diff_msgs_list.append(f"{child_path}: MISSING in actual (expected {expected[key]})")
                elif key not in expected:
                    diff_msgs_list.append(f"{child_path}: UNEXPECTED in actual (got {actual[key]})")
                else:
                    # values could be another dict, so we have to recursively compare it
                    diff_msgs_list.extend(_diff(actual[key], expected[key], child_path))

        elif isinstance(expected, (tuple, list)):
            if len(actual) != len(expected):
                diff_msgs_list.append(f"{path}: list length mismatch: got {len(actual)}, expected {len(expected)}")
            for i, (a_item, e_item) in enumerate(zip(actual, expected)):
                # values could be another list/tuple, so we have to recursively compare it
                diff_msgs_list.extend(_diff(a_item, e_item, f"{path}[{i}]"))
            # show extra/missing items
            if len(actual) > len(expected):
                for i, item in enumerate(actual[len(expected):], start=len(expected)):
                    diff_msgs_list.append(f"{path}[{i}]: UNEXPECTED in actual: {item}")
            elif len(expected) > len(actual):
                for i, item in enumerate(expected[len(actual):], start=len(actual)):
                    diff_msgs_list.append(f"{path}[{i}]: MISSING in actual: {item}")

        elif actual != expected:
            # values don't need to be recursively compared
            diff_msgs_list += [f"{path}"] if path != 'root' else []
            diff_msgs_list.append(f"expected: {expected}")
            diff_msgs_list.append(f"got:      {actual}")
        return diff_msgs_list

    return "\n".join(_diff(actual_value, expected_value, "root"))


# DMFA values that change from one run to another, masked in the JSON snapshots
DMFA_IGNORE_KEYS = (
    'NaturalPersonUserReference',  # hr.employee id
    'OccupationUserReference',  # hr.version id
    '@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation',  # depends on today's date
)


@tagged('post_install', '-at_install', 'dmfa')
@patch.object(CertificateCertificate, '_decode_certificate_for_be_onss_xml', lambda contract, xml_str: b'dummy\r\nsignature\r\n')
class TestDMFA(TestPayslipValidationCommon, TestBelgiumCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    @TestPayslipValidationCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.env.user.group_ids |= cls.env.ref('hr_payroll.group_hr_payroll_user') | cls.env.ref('fleet.fleet_group_manager')
        cls.payroll_manager = mail_new_test_user(cls.env, login='blou', groups='hr_payroll.group_hr_payroll_manager,fleet.fleet_group_manager')

        cls.belgian_company = cls.company_data['company']

        cls.belgian_company.write({
            'vat': 'BE0897223670',
            'phone': '0471098765',
            'street': 'Test street',
            'city': 'Test city',
            'zip': '8292',
            'country_id': cls.env.ref('base.be').id,
            'onss_expeditor_number': '123456',
        })
        cls.belgian_company.current_payroll_config_id.write({
            'l10n_be_revenue_code': '1234',
            'l10n_be_company_number': '0123456749',
            'onss_registration_number': '125482497',
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id,
            'l10n_be_main_joint_committee': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'onss_importance_code': '4',
        })

        cls.calendar_38h = cls.env['resource.calendar'].create({
            'name': 'Standard 38 hours/week',
            'company_id': cls.belgian_company.id,
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
        cls.belgian_company.resource_calendar_id = cls.calendar_38h
        cls.calendar_38h.write({'reference_calendar_id': cls.calendar_38h.id})

        cls.calendar_4_days_36_hours = cls.env['resource.calendar'].create([{
            'name': "Test Calendar: 4 days, 36 hours/week",
            'company_id': cls.belgian_company.id,
            'hours_per_day': 9,
            'full_time_required_hours': 36.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.be_work_entry_type_attendance').id,
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 12.0, 13.0),
                ("0", 13.0, 18),
                ("1", 8.0, 12.0),
                ("1", 12.0, 13.0),
                ("1", 13.0, 18),
                ("2", 8.0, 12.0),
                ("2", 12.0, 13.0),
                ("2", 13.0, 18),
                ("3", 8.0, 12.0),
                ("3", 12.0, 13.0),
                ("3", 13.0, 18),
            ]]
        }]).sudo(False)
        cls.calendar_4_days_36_hours.write({'reference_calendar_id': cls.calendar_4_days_36_hours.id})

        cls.calendar_4_5_wednesday_off = cls.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar: 4/5 Wednesday Off",
            'company_id': cls.belgian_company.id,
            'hours_per_day': 7.6,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.be_work_entry_type_attendance').id,
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time').id,
            }) for dayofweek, hour_from, hour_to in [
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
            ]],
        }]).sudo(False)

        cls.calendar_0_hours_per_week_credit_time = cls.env['resource.calendar'].create([{
            'name': "Test Calendar: 0 Hours per week",
            'company_id': cls.belgian_company.id,
            'hours_per_day': 0,
            'full_time_required_hours': 38,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_be_work_entry_type_credit_time').id,
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }])

        cls.calendar_0_hours_per_week_partial_incapacity = cls.env['resource.calendar'].create([{
            'name': "Test Calendar: 0 Hours per week",
            'company_id': cls.belgian_company.id,
            'hours_per_day': 0,
            'hours_per_week': 0,
            'full_time_required_hours': 38,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_be_work_entry_type_partial_incapacity').id,
            }) for dayofweek, hour_from, hour_to in [
                ("0", 8.0, 12.0),
                ("0", 13.0, 16.6),
                ("1", 8.0, 12.0),
                ("1", 13.0, 16.6),
                ("2", 8.0, 12.0),
                ("2", 13.0, 16.6),
                ("3", 8.0, 12.0),
                ("3", 13.0, 16.6),
                ("4", 8.0, 12.0),
                ("4", 13.0, 16.6),
            ]],
        }])

        cls.work_contact = cls.env['res.partner'].create({'name': 'Test Work Contact'})

        cls.brand = cls.env['fleet.vehicle.model.brand'].sudo().create({
            'name': "Test Brand"
        })

        cls.model = cls.env['fleet.vehicle.model'].sudo().create({
            'name': "Test Model",
            'brand_id': cls.brand.id
        })

        with freeze_time('2020-10-08'):
            cls.car = cls.env['fleet.vehicle'].sudo().create({
                'name': "Test Car",
                'license_plate': "TEST",
                'driver_id': cls.work_contact.id,
                'company_id': cls.belgian_company.id,
                'model_id': cls.model.id,
                'contract_date_start': date(2020, 10, 8),
                'co2': 88.0,
                'car_value': 38000.0,
                'fuel_type': "diesel",
                'acquisition_date': date(2020, 1, 1)
            }).sudo(False)

            cls.env['fleet.vehicle.log.contract'].sudo().create({
                'name': "Test Contract",
                'vehicle_id': cls.car.id,
                'company_id': cls.belgian_company.id,
                'start_date': date(2020, 10, 8),
                'expiration_date': date(2021, 10, 8),
                'state': "open",
                'cost_generated': 0.0,
                'cost_frequency': "monthly",
                'recurring_cost_amount_depreciated': 450.0
            })

        cls.cp200 = cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Laurie Poiret',
            'work_contact_id': cls.work_contact.id,
            'niss': '91111111192',
            'marital': 'single',
            'private_street': '58 rue des Wallons',
            'private_city': 'Louvain-la-Neuve',
            'private_zip': '1348',
            'private_country_id': cls.env.ref("base.be").id,
            'private_phone': '+0032476543210',
            'private_email': 'laurie.poiret@example.com',
            'resource_calendar_id': cls.calendar_38h.id,
            'company_id': cls.belgian_company.id,
            'car_id': cls.car.id,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2018, 12, 31),
            'date_version': date(2018, 12, 31),
            'wage': 3000,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_misc_base_amount': 283.73,
            'l10n_be_lsa_monthly_pro_other_amount': 16.27,
            'l10n_be_joint_committee_id': cls.cp200.id,
            # fully compensated: this suite doesn't test the annual sectorial bonus
            'l10n_be_sectorial_bonus_compensatory_amount': 1000.0,
            'lang': 'fr_BE',
        })
        cls.contract = cls.employee.version_id

        company = cls.employee.company_id
        cls.payroll_manager.company_ids = [(4, company.id)]
        cls.partner_wallonia = cls.env['res.partner'].create({'name': 'WA Work Address'})
        cls.env["hr.work.location"].with_user(cls.payroll_manager).search([
            ("address_id", "=", company.partner_id.id),
        ]).write({"bce_code": "8888888881", "location_type": "dmfa_unit"})
        cls.env['hr.work.location'].with_user(cls.payroll_manager).create({
            'company_id': cls.belgian_company.id,
            'bce_code': '8888888882',
            'location_type': 'dmfa_unit',
            'address_id': cls.partner_wallonia.id,
            'competence': 'wa',
        })

        cls.employee_2 = cls.env['hr.employee'].create({
            'name': 'Michael Demo',
            'work_contact_id': cls.work_contact.id,
            'niss': '91111111291',
            'marital': 'single',
            'private_street': '58 rue des Wallons',
            'private_city': 'Louvain-la-Neuve',
            'private_zip': '1348',
            'private_country_id': cls.env.ref("base.be").id,
            'private_phone': '+0032476543210',
            'private_email': 'michael.demo@example.com',
            'resource_calendar_id': cls.calendar_38h.id,
            'company_id': cls.belgian_company.id,
            'car_id': cls.car.id,
            'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
            'contract_date_start': date(2018, 12, 31),
            'date_version': date(2018, 12, 31),
            'wage': 3000,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_misc_base_amount': 283.73,
            'l10n_be_lsa_monthly_pro_other_amount': 16.27,
            'eco_checks': 250,
            'active': False,
        })
        # Activate the benefit
        cls.env['hr.contract.salary.benefit'].with_context(active_test=False).search([('res_field_id.name', 'in', ['l10n_be_lsa_monthly_pro_other_amount', 'l10n_be_lsa_monthly_misc_base_amount'])]).active = True

    def _assertDMFAEqual(self, dmfa_dict, ignore_keys=DMFA_IGNORE_KEYS, label=None):
        """
        Compare the DMFA dict with the JSON snapshot of the test
        (tests/test_files/dmfa/test_dmfa/<test method>.json), see
        TestPayrollBase._assert_dict_snapshot on how to (re)generate it.
        Volatile values (record ids, xsd version...) are masked with `ignore_keys`.
        """
        self._assert_dict_snapshot(
            dmfa_dict, 'dmfa', label=label, ignore_keys=ignore_keys, diff=get_variable_diff_as_message)

    @staticmethod
    def fake_time_object():
        today = datetime.now()
        day = today.strftime('%Y%m%d')
        hour = today.strftime('%H:%M:%S.%f')[:-3]
        return patch.object(time, 'strftime', lambda fmt, t: day if fmt == '%Y%m%d' else hour)

    def _generate_dmfa_declaration(self, environment='S', declaration_type='original', year='2025', quarter='1', parent=None, return_declaration=False, skip_signature=True):
        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TESTDMFA',
            'company_id': self.belgian_company.id,
            'year': year,
            'quarter': quarter,
            'declaration_method': 'batch',
            'declaration_type': declaration_type,
            'environment': environment,
            'parent_id': parent.id if parent else False,
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=skip_signature).generate_declaration_xml_report()
        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.state, 'ready')
        if return_declaration:
            return dmfa
        return xml_str_to_dict(dmfa.xml_file.content)

    def _get_ded3000(self, employee, payslips):
        occupation_data = employee.version_ids.sorted('date_start', reverse=True)._get_occupation_dates()
        occupation_groups = []
        ded3000_by_occupation = {}
        for versions, _, _ in occupation_data:
            slips = payslips.filtered(lambda p, versions=versions: p.version_id in versions)
            if slips:
                occupation_groups.append((versions, slips))
        mu_global = 0
        for _, slips in occupation_groups:
            mu_global += L10n_BeDmfa._get_l10n_be_mu(slips[:1].version_id, payslips=slips)
        for contracts, slips in occupation_groups:
            ded3000_by_occupation[contracts, slips] = L10n_BeDmfa._get_l10n_be_structural_deduction_3000(slips, mu_global)
        return ded3000_by_occupation

    @freeze_time("2025-04-10 10:00:00")
    def test_01_empty_dmfa(self):
        dmfa_dict = self._generate_dmfa_declaration()
        self._assertDMFAEqual(dmfa_dict)

    @freeze_time("2025-04-10 10:00:00")
    def test_02_declaration_classic_employee_with_commissions(self):
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)

        self.employee.write({'review_state': '1_reviewed'})
        for payslip in payslips:  # No batch compute and validate for ONSS regularization
            payslip.compute_sheet()
            payslip.action_payslip_done()

        self._validate_payslip(payslips[0])
        self._validate_payslip(payslips[1])
        self._validate_payslip(payslips[2])
        dmfa_dict = self._generate_dmfa_declaration()
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_03_declaration_employee_partial_credit_time(self):
        self.contract.contract_date_end = date(2025, 2, 28)
        contract_credit_time = self.env['hr.version'].create({
            'name': "Contract Credit Time",
            'employee_id': self.employee.id,
            'resource_calendar_id': self.calendar_4_5_wednesday_off.id,
            'reference_calendar_id': self.calendar_38h.id,
            'work_time_rate': 0.8,
            'company_id': self.belgian_company.id,
            'car_id': self.car.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date(2025, 3, 1),
            'contract_date_start': date(2025, 3, 1),
            'wage': 3000,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_misc_base_amount': 283.73,
            'l10n_be_lsa_monthly_pro_other_amount': 16.27,
            'l10n_be_joint_committee_id': self.cp200.id,
        })
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': contract_credit_time.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        for payslip in payslips:  # No batch compute and validate for ONSS regularization
            payslip.compute_sheet()
            payslip.action_payslip_done()
        self._validate_payslip(payslips[0])
        self._validate_payslip(payslips[1])
        self._validate_payslip(payslips[2])

        dmfa_dict = self._generate_dmfa_declaration()
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        natural_person = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        self.assertEqual(natural_person['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(natural_person['WorkerRecord']['Occupation'][0]['OccupationUserReference'], str(contract_credit_time.id))
        self.assertEqual(natural_person['WorkerRecord']['Occupation'][1]['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(71.66, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_04_declaration_employee_full_credit_time(self):
        self.contract.contract_date_end = date(2025, 2, 28)
        contract_credit_time = self.env['hr.version'].create({
            'name': "Contract Credit Time",
            'employee_id': self.employee.id,
            'resource_calendar_id': self.calendar_0_hours_per_week_credit_time.id,
            'reference_calendar_id': self.calendar_38h.id,
            'work_time_rate': 0,
            'company_id': self.belgian_company.id,
            'car_id': self.car.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date(2025, 3, 1),
            'contract_date_start': date(2025, 3, 1),
            'wage': 3000 * 4 / 5,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_misc_base_amount': 283.73,
            'l10n_be_lsa_monthly_pro_other_amount': 16.27,
            'l10n_be_joint_committee_id': self.cp200.id,
        })
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': contract_credit_time.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        for payslip in payslips:  # No batch compute and validate for ONSS regularization
            payslip.compute_sheet()
            payslip.action_payslip_done()
        self._validate_payslip(payslips[0])
        self._validate_payslip(payslips[1])
        self._validate_payslip(payslips[2])
        dmfa_dict = self._generate_dmfa_declaration()

        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        natural_person = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        occupations = natural_person['WorkerRecord']['Occupation']
        self.assertEqual(natural_person['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(occupations[0]['OccupationUserReference'], str(contract_credit_time.id))
        self.assertEqual(occupations[1]['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_05_declaration_employee_partial_incapacity(self):
        self.contract.contract_date_end = date(2025, 2, 28)
        contract_credit_time = self.env['hr.version'].create({
            'name': "Contract Credit Time",
            'employee_id': self.employee.id,
            'resource_calendar_id': self.calendar_0_hours_per_week_partial_incapacity.id,
            'reference_calendar_id': self.calendar_38h.id,
            'work_time_rate': 0,
            'company_id': self.belgian_company.id,
            'car_id': self.car.id,
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'date_version': date(2025, 3, 1),
            'contract_date_start': date(2025, 3, 1),
            'wage': 3000 * 4 / 5,
            'transport_mode_car': True,
            'fuel_card': 150.0,
            'internet': 38.0,
            'mobile': 30.0,
            'meal_voucher_amount': 7.45,
            'l10n_be_lsa_monthly_misc_base_amount': 283.73,
            'l10n_be_lsa_monthly_pro_other_amount': 16.27,
            'l10n_be_joint_committee_id': self.cp200.id,
        })
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': contract_credit_time.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        for payslip in payslips:  # No batch compute and validate for ONSS regularization
            payslip.compute_sheet()
            payslip.action_payslip_done()
        self._validate_payslip(payslips[0])
        self._validate_payslip(payslips[1])
        self._validate_payslip(payslips[2])
        dmfa_dict = self._generate_dmfa_declaration()
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        natural_person = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        occupations = natural_person['WorkerRecord']['Occupation']
        self.assertEqual(natural_person['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(occupations[0]['OccupationUserReference'], str(contract_credit_time.id))
        self.assertEqual(occupations[1]['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-11 10:00:00")
    def test_06_declaration_employee_no_notice_period(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 10),
            'l10n_be_notice_respect': 'without',
            'departure_description': 'foo',
            'action_date': date(2025, 2, 11),
        })
        self.contract.write({
            "contract_date_end": date(2025, 2, 10)
        })
        self.employee.write({
            'l10n_be_lsa_monthly_misc_base_amount': 0.0,
            'l10n_be_lsa_monthly_pro_base_amount': 283.73,
        })
        self.env['hr.contract.salary.benefit'].with_context(active_test=False).search([('res_field_id.name', '=', 'l10n_be_lsa_monthly_pro_base_amount')]).active = True

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips[0].compute_sheet()
        self._validate_payslip(payslips[0])
        payslips[0].action_payslip_done()
        payslips[1].compute_sheet()
        # incomplete month as the employee's last day on the 10th of february
        self._validate_payslip(payslips[1])
        payslips[1].action_payslip_done()

        self.employee.review_state = '1_reviewed'
        departure_notice._compute_payslip_history()
        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_payslip()
        departure_payslips += departure_notice._generate_termination_holidays()

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda pay: pay.struct_id == struct_id)
        termination_fees_payslip.compute_sheet()
        self._validate_payslip(termination_fees_payslip)

        # Holiday Attests
        structure_holidays_n = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        structure_holidays_n1 = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')
        holiday_pay_n = departure_payslips.filtered(lambda pay: pay.struct_id == structure_holidays_n)
        holiday_pay_n1 = departure_payslips.filtered(lambda pay: pay.struct_id == structure_holidays_n1)
        self._validate_payslip(holiday_pay_n)
        self._validate_payslip(holiday_pay_n1)
        departure_payslips.action_payslip_done()

        thirteen_month_payslip = self.env['hr.payslip'].create({
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
            'company_id': self.belgian_company.id,
        })
        thirteen_month_payslip._set_input_value('MONTH', 8)
        thirteen_month_payslip.compute_sheet()
        self._validate_payslip(thirteen_month_payslip)
        self.employee.write({'review_state': '1_reviewed'})
        thirteen_month_payslip.action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    def _set_declaration_employee_no_notice_period(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 10),
            'l10n_be_notice_respect': 'without',
            'departure_description': 'foo',
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Sep 2024',
            'version_id': self.contract.id,
            'date_from': datetime(2024, 9, 1),
            'date_to': datetime(2024, 9, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Oct 2024',
            'version_id': self.contract.id,
            'date_from': datetime(2024, 10, 1),
            'date_to': datetime(2024, 10, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Nov 2024',
            'version_id': self.contract.id,
            'date_from': datetime(2024, 11, 1),
            'date_to': datetime(2024, 11, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Dec 2024',
            'version_id': self.contract.id,
            'date_from': datetime(2024, 12, 1),
            'date_to': datetime(2024, 12, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips.compute_sheet()
        payslips.action_payslip_done()
        departure_notice._compute_payslip_history()
        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_payslip()
        departure_payslips += departure_notice._generate_termination_holidays()
        return [('id', 'in', departure_payslips.ids)]

    @freeze_time("2025-05-11 10:00:00")
    def test_06_bis_declaration_employee_no_notice_period_with_special_contributions_part_time(self):
        self.employee.wage = 4500  # force the wage to be high enough to trigger special contributions
        self.employee.resource_calendar_id = self.calendar_4_5_wednesday_off
        self.employee.reference_calendar_id = self.calendar_38h
        payslips_domain = self._set_declaration_employee_no_notice_period()

        departure_payslips = self.env['hr.payslip'].search(payslips_domain)

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda pay: pay.struct_id == struct_id)
        termination_fees_payslip.compute_sheet()
        self._validate_payslip(termination_fees_payslip)

        self.employee.write({'review_state': '1_reviewed'})
        termination_fees_payslip.action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        result_line = next(line for line in dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['WorkerContribution'] if line['ContributionWorkerCode'] == '812')
        expected_line = {'ContributionWorkerCode': '812', 'ContributionType': '1', 'ContributionCalculationBasis': '00002666539', 'ContributionAmount': '00000026665'}
        self.assertDictEqual(expected_line, result_line)

    @freeze_time("2025-05-11 10:00:00")
    def test_06_bis_declaration_employee_no_notice_period_with_special_contributions(self):
        self.employee.wage = 4500  # force the wage to be high enough to trigger special contributions
        payslips_domain = self._set_declaration_employee_no_notice_period()

        departure_payslips = self.env['hr.payslip'].search(payslips_domain)

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda pay: pay.struct_id == struct_id)
        termination_fees_payslip.compute_sheet()
        self._validate_payslip(termination_fees_payslip)

        self.employee.write({'review_state': '1_reviewed'})
        termination_fees_payslip.action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        result_line = next(line for line in dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['WorkerContribution'] if line['ContributionWorkerCode'] == '812')
        expected_line = {'ContributionWorkerCode': '812', 'ContributionType': '1', 'ContributionCalculationBasis': '00002679895', 'ContributionAmount': '00000026799'}
        self.assertDictEqual(expected_line, result_line)

    @freeze_time("2025-05-11 10:00:00")
    def test_06_bis_declaration_employee_no_notice_period_with_special_contributions_multiple_empty_quarters(self):
        self.employee.wage = 4500  # force the wage to be high enough to trigger special contributions

        # Create two full quarters without remuneration
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'request_date_from': date(2024, 10, 1),
            'request_date_to': date(2025, 3, 31),
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
        })

        payslips_domain = self._set_declaration_employee_no_notice_period()

        departure_payslips = self.env['hr.payslip'].search(payslips_domain)

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda pay: pay.struct_id == struct_id)
        termination_fees_payslip.compute_sheet()
        self._validate_payslip(termination_fees_payslip)

        # Should iterate beyond the previous quarter(s)
        yearly_salary = termination_fees_payslip._l10n_be_get_termination_yearly_salary()
        self.assertGreater(yearly_salary, 0)

        self.employee.write({'review_state': '1_reviewed'})
        termination_fees_payslip.action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        result_line = next(line for line in dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['WorkerContribution'] if line['ContributionWorkerCode'] == '812')
        expected_line = {'ContributionWorkerCode': '812', 'ContributionType': '1', 'ContributionCalculationBasis': '00002679895', 'ContributionAmount': '00000026799'}
        self.assertDictEqual(expected_line, result_line)

    @freeze_time("2025-05-11 10:00:00")
    def test_06_bis_declaration_employee_no_notice_period_with_special_contributions_before_2014(self):
        """
        TERM_BASIC = 62351.11
        As this employee started before 2014, their cotisation_812 should be calculated only for the period after 2024
        So on his 5155 worked days, his cotisation_812 will be applied only on 4058 days
        So his cotisation basis will be 62351.11 * 4058 / 5155 = 49082.60
        so his cotisation_812 will be equal to 490.83
        """
        self.employee.wage = 4500  # force the wage to be high enough to trigger special contributions
        self.employee.contract_date_start = date(2010, 12, 31)
        self.employee.date_version = date(2010, 12, 31)
        payslips_domain = self._set_declaration_employee_no_notice_period()
        departure_payslips = self.env['hr.payslip'].search(payslips_domain)

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda pay: pay.struct_id == struct_id)
        termination_fees_payslip.compute_sheet()

        self._validate_payslip(termination_fees_payslip)

        self.employee.write({'review_state': '1_reviewed'})
        termination_fees_payslip.action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        result_line = next(line for line in dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['WorkerContribution'] if line['ContributionWorkerCode'] == '812')
        expected_line = {'ContributionWorkerCode': '812', 'ContributionType': '1', 'ContributionCalculationBasis': '00004922412', 'ContributionAmount': '00000049224'}
        self.assertDictEqual(expected_line, result_line)

    @classmethod
    def _get_dmfa_original_xsd(cls):
        """
        Part of the DMFA (for e.g.:)
        expected_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation']
        would change values according to today's date.
        This function returns the correct value assuming the DMFA has been
        generated today.
        """
        target_date = date.today() - relativedelta(months=3)
        target_quarter = (target_date.month - 1) // 3 + 1
        current_year_quarter = '%s%s' % (target_date.year, target_quarter)
        return 'DmfAOriginal_' + current_year_quarter + '.xsd'

    @freeze_time("2026-07-01 10:00:00")
    def test_07_declaration_employee_notice_period(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 10),
            'l10n_be_notice_respect': 'with',
            'departure_description': 'foo',
            'action_date': date(2025, 2, 11),
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips[0].compute_sheet()
        self._validate_payslip(payslips[0])
        payslips[0].action_payslip_done()
        payslips[1].compute_sheet()
        self._validate_payslip(payslips[1])
        payslips[1].action_payslip_done()

        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_holidays()

        # Termination Fees
        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda dep: dep.struct_id == struct_id)
        self.assertFalse(termination_fees_payslip, "There should not be a termination fees payslip as the employee is doing his departure notice.")

        # Holiday Attests
        structure_holidays_n = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n_holidays')
        structure_holidays_n1 = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_departure_n1_holidays')
        holiday_pay_n = departure_payslips.filtered(lambda pay: pay.struct_id == structure_holidays_n)
        holiday_pay_n1 = departure_payslips.filtered(lambda pay: pay.struct_id == structure_holidays_n1)
        self._validate_payslip(holiday_pay_n)
        self._validate_payslip(holiday_pay_n1)

        thirteen_month_payslip = self.env['hr.payslip'].create({
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
            'company_id': self.belgian_company.id,
        })
        thirteen_month_payslip._set_input_value('MONTH', 8)
        thirteen_month_payslip.compute_sheet()
        self._validate_payslip(thirteen_month_payslip)
        self.employee.write({'review_state': '1_reviewed'})
        (payslips + termination_fees_payslip + holiday_pay_n + holiday_pay_n1 + thirteen_month_payslip)._compute_issues()
        (payslips + termination_fees_payslip + holiday_pay_n + holiday_pay_n1 + thirteen_month_payslip).action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self._assertDMFAEqual(dmfa_dict, ignore_keys=DMFA_IGNORE_KEYS + ('FormCreationDate',))
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_08_declaration_structural_reductions_3000(self):
        self.contract.wage = 2000
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        for payslip in payslips:  # No batch compute and validate for ONSS regularization
            payslip.compute_sheet()
            payslip.action_payslip_done()
        self._validate_payslip(payslips[0])
        self._validate_payslip(payslips[1])
        self._validate_payslip(payslips[2])
        dmfa_dict = self._generate_dmfa_declaration()
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslips)
        self.assertIn(395.65, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2026-12-30 10:00:00")
    def test_09_declaration_regularization_code_12_recovery(self):
        self.employee.l10n_be_holiday_attest_ids = [
            Command.create({
                'date_from': date(2025, 1, 1),
                'date_to': date(2025, 12, 31),
                "prev_work_time_rate": 1,
                "prev_work_days_per_week": 5,
                "prev_days_earned": 10,
                "prev_simple_holiday_pay_paid": 2000,
                "prev_double_holiday_pay_paid": 0,
            }),
        ]
        self.contract.contract_date_start = date(2025, 1, 1)
        self.contract.wage = 2000

        self.env['resource.calendar.leaves'].create([{
            'name': "Legal Leave Nov",
            'calendar_id': self.calendar_38h.id,
            'company_id': self.belgian_company.id,
            'resource_id': self.employee.resource_id.id,
            'date_from': datetime(2026, 11, 2, 6, 0, 0),
            'date_to': datetime(2026, 11, 6, 19, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_legal_leave').id
        }, {
            'name': "Legal Leave Dec",
            'calendar_id': self.calendar_38h.id,
            'company_id': self.belgian_company.id,
            'resource_id': self.employee.resource_id.id,
            'date_from': datetime(2026, 12, 7, 6, 0, 0),
            'date_to': datetime(2026, 12, 11, 19, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_legal_leave').id
        }])

        self.employee.write({'review_state': '1_reviewed'})

        for month in range(9, 13):
            payslip = self.env['hr.payslip'].create({
                'version_id': self.contract.id,
                'date_from': datetime(2026, month, 1),
                'date_to': datetime(2026, month, 30 if month in (9, 11) else 31),
                'employee_id': self.employee.id,
                'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
                'company_id': self.belgian_company.id,
            })
            payslip.compute_sheet()
            payslip.action_payslip_done()

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TEST_REG_12',
            'company_id': self.belgian_company.id,
            'year': '2026',
            'quarter': '4',
            'declaration_method': 'batch',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()

        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        natural_person = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        self.assertEqual(natural_person['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(natural_person['WorkerRecord']['Occupation']['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, self.employee.slip_ids.filtered(lambda s: date_utils.get_quarter_number(s.date_from) == 4))
        self.assertIn(1422.45, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2026-12-30 10:00:00")
    def test_10_declaration_regularization_code_14_reimbursement(self):
        self.employee.l10n_be_holiday_attest_ids = [
            Command.create({
                'date_from': date(2025, 1, 1),
                'date_to': date(2025, 12, 31),
                "prev_work_time_rate": 1,
                "prev_work_days_per_week": 5,
                "prev_days_earned": 10,
                "prev_simple_holiday_pay_paid": 500,
                "prev_double_holiday_pay_paid": 0,
            }),
        ]
        self.contract.contract_date_start = date(2025, 1, 1)
        self.contract.wage = 4000

        self.env['resource.calendar.leaves'].create([{
            'name': "Legal Leave Nov",
            'calendar_id': self.calendar_38h.id,
            'company_id': self.belgian_company.id,
            'resource_id': self.employee.resource_id.id,
            'date_from': datetime(2026, 11, 2, 6, 0, 0),
            'date_to': datetime(2026, 11, 6, 19, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_legal_leave').id
        }, {
            'name': "Legal Leave Dec",
            'calendar_id': self.calendar_38h.id,
            'company_id': self.belgian_company.id,
            'resource_id': self.employee.resource_id.id,
            'date_from': datetime(2026, 12, 7, 6, 0, 0),
            'date_to': datetime(2026, 12, 11, 19, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_legal_leave').id
        }])

        self.employee.write({'review_state': '1_reviewed'})

        for month in range(9, 13):
            payslip = self.env['hr.payslip'].create({
                'version_id': self.contract.id,
                'date_from': datetime(2026, month, 1),
                'date_to': datetime(2026, month, 30 if month in (9, 11) else 31),
                'employee_id': self.employee.id,
                'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
                'company_id': self.belgian_company.id,
            })
            payslip.compute_sheet()
            payslip.action_payslip_done()

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TEST_REG_14',
            'company_id': self.belgian_company.id,
            'year': '2026',
            'quarter': '4',
            'declaration_method': 'batch',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()

        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        natural_person = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        self.assertEqual(natural_person['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(natural_person['WorkerRecord']['Occupation']['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, self.employee.slip_ids.filtered(lambda s: date_utils.get_quarter_number(s.date_from) == 4))
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2026-01-01 10:00:00")
    def test_09_declaration_no_worked_days_lines(self):
        self.contract.wage = 2000
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 10, 1),
            'request_date_to': date(2025, 12, 31),
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
        })
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        },
        {
            'name': 'Payslip Oct 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 10, 1),
            'date_to': datetime(2025, 10, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Nov 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 11, 1),
            'date_to': datetime(2025, 11, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Dec 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 12, 1),
            'date_to': datetime(2025, 12, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'PFA',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 12, 1),
            'date_to': datetime(2025, 12, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_thirteen_month').id,
            'company_id': self.belgian_company.id,
        }])
        payslips.compute_sheet()
        payslips.action_payslip_done()
        dmfa_dict = self._generate_dmfa_declaration(quarter='4')
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)

    @freeze_time("2026-06-01 10:00:00")
    def test_11_voluntary_overtime(self):
        # Fully compensate the annual sectoral bonus so it stays out of the ONSS
        # base: this test covers voluntary overtime, not the sectoral bonus.
        self.contract.l10n_be_sectorial_bonus_compensatory_amount = 1000
        self.env['hr.leave'].create([{
            'employee_id': self.employee.id,
            'request_date_from': date(2026, 6, 1),
            'request_date_to': date(2026, 6, 1),
            'request_hour_from': 19,
            'request_hour_to': 23,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_net').id,
            'company_id': self.belgian_company.id,
        }, {
            'employee_id': self.employee.id,
            'request_date_from': date(2026, 6, 2),
            'request_date_to': date(2026, 6, 2),
            'request_hour_from': 19,
            'request_hour_to': 23,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_150').id,
            'company_id': self.belgian_company.id,
        }, {
            'employee_id': self.employee.id,
            'request_date_from': date(2026, 6, 3),
            'request_date_to': date(2026, 6, 3),
            'request_hour_from': 19,
            'request_hour_to': 23,
            'work_entry_type_id': self.env.ref('hr_work_entry.l10n_be_work_entry_type_voluntary_overtime_200').id,
            'company_id': self.belgian_company.id,
        }])
        # leave.action_approve()
        payslip = self.env['hr.payslip'].create({
            'version_id': self.contract.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()
        payslip.action_payslip_done()
        self._validate_payslip(payslip)
        dmfa_dict = self._generate_dmfa_declaration(year="2026", quarter="2")
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], str(self.employee.id))
        self.assertEqual(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], str(self.contract.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(self.employee, payslip)
        self.assertIn(152.96, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_13_declaration_employee_partial_notice_period(self):
        departure_notice = self.env['hr.employee.departure'].create({
            'employee_id': self.employee.id,
            'departure_reason_id': self.env.ref('hr.departure_fired').id,
            'dismissal_date': date(2025, 2, 10),
            'departure_date': date(2025, 2, 28),
            'l10n_be_notice_respect': 'partial',
            'departure_description': 'foo',
            'action_date': date(2025, 3, 1),
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        departure_notice._compute_payslip_history()
        departure_notice.action_register()
        departure_payslips = departure_notice._generate_termination_payslip()
        departure_payslips += departure_notice._generate_termination_holidays()

        struct_id = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_termination_fees')
        termination_fees_payslip = departure_payslips.filtered(lambda pay: pay.struct_id == struct_id)
        termination_fees_payslip.compute_sheet()

        (payslips + departure_payslips)._compute_issues()
        (payslips + departure_payslips).action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration()
        self._assertDMFAEqual(dmfa_dict, ignore_keys=DMFA_IGNORE_KEYS + ('NOSSRegistrationNbr', 'CompanyID'))

    @freeze_time("2025-04-10 10:00:00")
    def test_90_dmfa_sftp_flow_invalid_acrf(self):
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        # Generate DmfA record
        self.belgian_company.sudo().onss_certificate_id = self.env['certificate.certificate'].create({})
        dmfa = self._generate_dmfa_declaration(environment='T', return_declaration=True, skip_signature=False)
        self.assertTrue(dmfa.xml_file)
        self.assertTrue(dmfa.go_file)
        self.assertTrue(dmfa.signature_file)

        # 1. Generate DmfA SFTP declaration, invalid ACRF
        dmfa.create_onss_declaration()
        declaration = dmfa.onss_declaration_ids
        self.assertEqual(dmfa.onss_declaration_count, 1)
        self.assertEqual(declaration.onss_file_count, 3)

        # Post DmfA SFTP declaration to ONSS
        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, signaling an invalid signature
        def mock_listdir_declaration_1(folder):
            if folder in ('OUT', 'OUTTEST-S'):
                return []
            elif folder == 'OUTTEST':
                return [
                    'FO.ACRF.999999.20250410.99999.T',
                    'FS.ACRF.999999.20250410.99999.T',
                    'GO.ACRF.999999.20250410.99999.T',
                ]

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_1(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20250410.99999.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20251.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2025-04-10</FormCreationDate>
        <FormCreationHour>15:36:40.276</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>03804UDVFMW3Z</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>0</ResultCode>
            <ErrorID>ACRF-125</ErrorID>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20250410.99999.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20250410.99999.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_1
            fake_sftp.file.side_effect = file_side_effect_declaration_1

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUTTEST/FO.ACRF.999999.20250410.99999.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/FS.ACRF.999999.20250410.99999.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/GO.ACRF.999999.20250410.99999.T', mode='rb')

        self.assertEqual(declaration.state, 'error')
        self.assertEqual(declaration.error_message, 'ACRF-125\nInvalid signature')
        self.assertEqual(declaration.onss_file_count, 6)

    @freeze_time("2025-04-10 10:00:00")
    def test_91_dmfa_sftp_flow_invalid_noti(self):
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        # Generate DmfA record
        self.belgian_company.sudo().onss_certificate_id = self.env['certificate.certificate'].create({})
        dmfa = self._generate_dmfa_declaration(environment='T', return_declaration=True, skip_signature=False)
        self.assertTrue(dmfa.xml_file)
        self.assertTrue(dmfa.go_file)
        self.assertTrue(dmfa.signature_file)

        # Generate DmfA SFTP declaration, valid ACRF
        dmfa.create_onss_declaration()
        declaration = dmfa.onss_declaration_ids
        self.assertEqual(dmfa.onss_declaration_count, 1)
        self.assertEqual(declaration.onss_file_count, 3)

        # Post DmfA SFTP declaration to ONSS
        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, ok
        def mock_listdir_declaration_2(folder):
            if folder == 'OUTTEST':
                return [
                    'FO.ACRF.999999.20250410.99998.T',
                    'FS.ACRF.999999.20250410.99998.T',
                    'GO.ACRF.999999.20250410.99998.T',
                ]
            return []

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_2(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20250410.99998.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20251.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2025-04-10</FormCreationDate>
        <FormCreationHour>12:05:55.075</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>03804UE9XCMQZ</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20250410.99998.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20250410.99998.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_2
            fake_sftp.file.side_effect = file_side_effect_declaration_2

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUTTEST/FO.ACRF.999999.20250410.99998.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/FS.ACRF.999999.20250410.99998.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/GO.ACRF.999999.20250410.99998.T', mode='rb')

        self.assertEqual(declaration.state, 'received')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 6)

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_1(folder):
            if folder in ('OUT', 'OUTTEST-S'):
                return []
            elif folder == 'OUTTEST':
                return [
                    'FO.NOTI.999999.20250410.99998.T',
                    'FS.NOTI.999999.20250410.99998.T',
                    'GO.NOTI.999999.20250410.99998.T',
                ]

        def file_side_effect_notification_1(remote_path, mode='rb'):
            if remote_path.endswith('FO.NOTI.999999.20250410.99998.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?><NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="NOTIFICATION_20251.xsd">
  <Form>
    <Identification>NOTI001</Identification>
    <FormCreationDate>2025-04-10</FormCreationDate>
    <FormCreationHour>16:35:16.359</FormCreationHour>
    <AttestationStatus>0</AttestationStatus>
    <TypeForm>FA</TypeForm>
    <FileReference>
      <FileName>%(go_filename)s</FileName>
      <ReferenceOrigin>2</ReferenceOrigin>
      <ReferenceNbr>03804UAVJS3PZ</ReferenceNbr>
    </FileReference>
    <HandledOriginalForm>
      <Identification>DMFA</Identification>
      <FormCreationDate>2025-04-10</FormCreationDate>
      <FormCreationHour>14:34:30.000</FormCreationHour>
      <AttestationStatus>0</AttestationStatus>
      <TypeForm>SU</TypeForm>
    </HandledOriginalForm>
    <Reference>
      <ReferenceType>1</ReferenceType>
      <ReferenceOrigin>1</ReferenceOrigin>
      <ReferenceNbr>2025/1</ReferenceNbr>
    </Reference>
    <EmployerId>
      <NOSSRegistrationNbr>125482497</NOSSRegistrationNbr>
      <CompanyID>0123456749</CompanyID>
    </EmployerId>
    <ConcernedQuarter>
      <Quarter>20251</Quarter>
    </ConcernedQuarter>
    <HandledReference>
      <ReferenceType>1</ReferenceType>
      <ReferenceOrigin>2</ReferenceOrigin>
      <ReferenceNbr>0340822PQ9CMZ</ReferenceNbr>
    </HandledReference>
    <WorkerRecordIdentification>
      <Quarter>20251</Quarter>
      <NOSSRegistrationNbr>125482497</NOSSRegistrationNbr>
      <CompanyID>0123456749</CompanyID>
      <NaturalPersonSequenceNbr>1</NaturalPersonSequenceNbr>
      <INSS>91111111192</INSS>
      <EmployerClass>578</EmployerClass>
      <WorkerCode>495</WorkerCode>
    </WorkerRecordIdentification>
    <HandlingResult>
      <ResultCode>0</ResultCode>
      <AnomalyReport>
        <ErrorID>00011-155</ErrorID>
        <TagName>NOSSRegistrationNbr</TagName>
        <Value>125482497</Value>
        <AnomalyClass>B</AnomalyClass>
        <AnomalyLocation>
          <Location>1,1,7,2</Location>
        </AnomalyLocation>
      </AnomalyReport>
    </HandlingResult>
  </Form>
</NOTIFICATION>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.NOTI.999999.20250410.99998.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.NOTI.999999.20250410.99998.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_1
            fake_sftp.file.side_effect = file_side_effect_notification_1

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUTTEST/FO.NOTI.999999.20250410.99998.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/FS.NOTI.999999.20250410.99998.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/GO.NOTI.999999.20250410.99998.T', mode='rb')

        self.assertEqual(declaration.state, 'error')
        self.assertEqual(declaration.error_message, 'Declaration rejected - blocking anomalies\nAnomaly (1/1) - Code: 00011-155\nNo or no longer a mandate\n- Tag Name: NOSSRegistrationNbr\n- Value: 125482497\n- NISS: False\n- Anomaly Class: Blocking anomaly\n\n')
        self.assertEqual(declaration.onss_file_count, 9)

    @freeze_time("2025-04-10 10:00:00")
    def test_92_dmfa_sftp_flow_valid_noti(self):
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips[0]._set_input_value('COMMISSION', 2000)
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        # Generate DmfA record
        self.belgian_company.sudo().onss_certificate_id = self.env['certificate.certificate'].create({})
        dmfa = self._generate_dmfa_declaration(environment='T', return_declaration=True, skip_signature=False)
        self.assertTrue(dmfa.xml_file)
        self.assertTrue(dmfa.go_file)
        self.assertTrue(dmfa.signature_file)

        # Generate DmfA SFTP declaration, valid ACRF, valid NOTI
        dmfa.create_onss_declaration()
        declaration = dmfa.onss_declaration_ids
        self.assertEqual(dmfa.onss_declaration_count, 1)
        self.assertEqual(declaration.onss_file_count, 3)

        # Post DmfA SFTP declaration to ONSS
        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, ok
        def mock_listdir_declaration_3(folder):
            if folder == 'OUTTEST':
                return [
                    'FO.ACRF.999999.20250410.99997.T',
                    'FS.ACRF.999999.20250410.99997.T',
                    'GO.ACRF.999999.20250410.99997.T',
                ]
            return []

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_3(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20250410.99997.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20251.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2025-04-10</FormCreationDate>
        <FormCreationHour>12:05:55.075</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>03804UE9XCMQZ</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20250410.99997.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20250410.99997.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_3
            fake_sftp.file.side_effect = file_side_effect_declaration_3

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUTTEST/FO.ACRF.999999.20250410.99997.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/FS.ACRF.999999.20250410.99997.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/GO.ACRF.999999.20250410.99997.T', mode='rb')

        self.assertEqual(declaration.state, 'received')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 6)

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_2(folder):
            if folder in ('OUT', 'OUTTEST-S'):
                return []
            elif folder == 'OUTTEST':
                return [
                    'FO.NOTI.999999.20250410.99997.T',
                    'FS.NOTI.999999.20250410.99997.T',
                    'GO.NOTI.999999.20250410.99997.T',
                ]

        def file_side_effect_notification_2(remote_path, mode='rb'):
            dmfa_onss_file = declaration.onss_file_ids.filtered(lambda f: f.declaration_type == 'DMFA' and f.file_type == 'FI')
            if remote_path.endswith('FO.NOTI.999999.20250410.99997.T'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?><NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="NOTIFICATION_20251.xsd">
<Form>
    <Identification>NOTI001</Identification>
    <FormCreationDate>2025-04-10</FormCreationDate>
    <FormCreationHour>21:48:14.795</FormCreationHour>
    <AttestationStatus>0</AttestationStatus>
    <TypeForm>FA</TypeForm>
    <HandledOriginalForm>
      <Identification>DMFA</Identification>
      <FormCreationDate>%(form_creation_date)s</FormCreationDate>
      <FormCreationHour>%(form_creation_hour)s</FormCreationHour>
      <AttestationStatus>0</AttestationStatus>
      <TypeForm>SU</TypeForm>
    </HandledOriginalForm>
    <Reference>
      <ReferenceType>1</ReferenceType>
      <ReferenceOrigin>1</ReferenceOrigin>
      <ReferenceNbr>2025/1</ReferenceNbr>
    </Reference>
<EmployerId>
      <NOSSRegistrationNbr>125482497</NOSSRegistrationNbr>
      <CompanyID>0123456749</CompanyID>
    </EmployerId>
    <ConcernedQuarter>
      <Quarter>20251</Quarter>
    </ConcernedQuarter>
<HandledReference>
      <ReferenceType>1</ReferenceType>
      <ReferenceOrigin>2</ReferenceOrigin>
      <ReferenceNbr>034081YBAQWPZ</ReferenceNbr>
    </HandledReference>
    <DeclarationComplInformations>
      <DMFAWorkersNbr>1</DMFAWorkersNbr>
      <DIMONAWorkersNbr>1</DIMONAWorkersNbr>
    </DeclarationComplInformations>
    <HandlingResult>
      <ResultCode>1</ResultCode>
      <AnomalyReport>
        <ErrorID>90007-262</ErrorID>
        <AnomalyClass>NP</AnomalyClass>
        <AnomalyLabel>Déclaration employeur - Plus de travailleurs déclarés en DmfA qu'en DIMONA</AnomalyLabel>
        <Path>
          <Quarter>20251</Quarter>
          <NOSSRegistrationNbr>125482497</NOSSRegistrationNbr>
          <Trusteeship>0</Trusteeship>
          <CompanyID>0123456749</CompanyID>
        </Path>
      </AnomalyReport>
      <AnomalyReport>
        <ErrorID>90001-476</ErrorID>
        <AnomalyClass>NP</AnomalyClass>
        <AnomalyLabel>Cotisation due pour la ligne travailleur - Cotisation spéciale sur les indemnités de rupture non présente</AnomalyLabel>
        <Path>
          <Quarter>20251</Quarter>
          <NOSSRegistrationNbr>125482497</NOSSRegistrationNbr>
          <Trusteeship>0</Trusteeship>
          <CompanyID>0123456749</CompanyID>
          <NaturalPersonSequenceNbr>1</NaturalPersonSequenceNbr>
          <INSS>91111111192</INSS>
          <EmployerClass>010</EmployerClass>
          <WorkerCode>495</WorkerCode>
          <NaturalPersonUserReference>4482041</NaturalPersonUserReference>
        </Path>
      </AnomalyReport>
    </HandlingResult>
  </Form>
</NOTIFICATION>""" % {'form_creation_date': dmfa_onss_file.form_creation_date, 'form_creation_hour': dmfa_onss_file.form_creation_hour}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.NOTI.999999.20250410.99997.T'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.NOTI.999999.20250410.99997.T'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_2
            fake_sftp.file.side_effect = file_side_effect_notification_2

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUTTEST/FO.NOTI.999999.20250410.99997.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/FS.NOTI.999999.20250410.99997.T', mode='rb')
            fake_sftp.file.assert_any_call('OUTTEST/GO.NOTI.999999.20250410.99997.T', mode='rb')

        self.assertEqual(declaration.state, 'notified')
        self.assertEqual(declaration.error_message, 'Anomaly (1/2) - Code: 90007-262\nMore workers declared in DmfA than in DIMONA\n- NISS: False\n- Anomaly Class: Non-percentage-based anomaly\n\n\nAnomaly (2/2) - Code: 90001-476\nSpecial contribution on severance pay not present\n- Employee: Laurie Poiret (NISS: 91111111192)\n- Anomaly Class: Non-percentage-based anomaly\n\n')
        self.assertEqual(declaration.onss_file_count, 9)

    @freeze_time("2025-04-10 10:00:00")
    def test_10_dmfa_groups_duplicate_niss_into_single_natural_person(self):

        def _sort_occupations(dmfa_dict):
            occupations = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord'][
                'Occupation']
            occupations.sort(key=lambda o: int(o['OccupationUserReference']))

        niss = '91111111192'
        first_employee, second_employee = self.env['hr.employee'].create([
            {
                'name': 'Employee 1',
                'company_id': self.belgian_company.id,
                'country_id': self.env.ref('base.be').id,
                'niss': niss,
                'contract_date_start': datetime(2020, 1, 1),
                'contract_date_end': None,
                'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
                'work_contact_id': self.work_contact.id,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'lang': 'fr_BE',
            },
            {
                'name': 'Employee 2',
                'company_id': self.belgian_company.id,
                'country_id': self.env.ref('base.be').id,
                'niss': niss,
                'contract_date_start': datetime(2020, 1, 1),
                'contract_date_end': None,
                'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
                'work_contact_id': self.work_contact.id,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'lang': 'fr_BE',
            }
        ]).sorted('id')

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 %s',
            'version_id': first_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': first_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jan 2025',
            'version_id': second_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': second_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id}])
        payslips.compute_sheet()
        first_employee.write({'review_state': '1_reviewed'})
        second_employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()
        dmfa_dict = self._generate_dmfa_declaration()
        _sort_occupations(dmfa_dict)
        self.assertEqual(dmfa_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        natural_person = dmfa_dict["DmfAOriginal"]["Form"]["EmployerDeclaration"]["NaturalPerson"]
        occupations = natural_person["WorkerRecord"]["Occupation"]
        self.assertEqual(natural_person["NaturalPersonUserReference"], str(first_employee.id))
        self.assertEqual(occupations[0]["OccupationUserReference"], str(first_employee.version_id.id))
        self.assertEqual(occupations[1]["OccupationUserReference"], str(second_employee.version_id.id))
        self._assertDMFAEqual(dmfa_dict)
        ded3000 = self._get_ded3000(first_employee, payslips[0])
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")
        ded3000 = self._get_ded3000(second_employee, payslips[1])
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    def test_93_dmfa_WorkingDaysSystems_4_days_week(self):
        self.belgian_company.resource_calendar_id = self.calendar_4_days_36_hours
        self.contract.reference_calendar_id = self.calendar_4_days_36_hours
        self.contract.resource_calendar_id = self.calendar_4_days_36_hours
        payslip = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 1, 31),
                       'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslip.compute_sheet()
        payslip.action_payslip_done()
        dmfa_dict = self._generate_dmfa_declaration()
        self.assertEqual(
            dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['WorkingDaysSystem'],
            '400'
        )

    @freeze_time("2025-04-10 10:00:00")
    def test_11_remove_employee_from_dmfa(self):
        first_employee, second_employee = self.env['hr.employee'].create([
            {
                'name': 'Employee 1',
                'company_id': self.belgian_company.id,
                'country_id': self.env.ref('base.be').id,
                'niss': '91111111192',
                'contract_date_start': datetime(2020, 1, 1),
                'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
                'work_contact_id': self.work_contact.id,
                'wage': 3000,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'lang': 'fr_BE',
            },
            {
                'name': 'Employee 2',
                'company_id': self.belgian_company.id,
                'country_id': self.env.ref('base.be').id,
                'niss': '99010112390',
                'contract_date_start': datetime(2020, 1, 1),
                'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
                'work_contact_id': self.work_contact.id,
                'wage': 4000,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'lang': 'fr_BE',
            }
        ])

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 - First employee',
            'version_id': first_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': first_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jan 2025 - Second employee',
            'version_id': second_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': second_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id}])
        payslips.compute_sheet()
        first_employee.write({'review_state': '1_reviewed'})
        second_employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TESTDMFA',
            'company_id': self.belgian_company.id,
            'year': '2025',
            'quarter': '1',
            'declaration_method': 'batch',
            'declaration_type': 'original',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()
        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.state, 'ready')
        dmfa_with_all_employees_dict = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_with_all_employees_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_with_all_employees_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson'][0]['NaturalPersonUserReference'], str(first_employee.id))
        self.assertEqual(dmfa_with_all_employees_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson'][0]['WorkerRecord']['Occupation']['OccupationUserReference'], str(first_employee.version_id.id))
        self.assertEqual(dmfa_with_all_employees_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson'][1]['NaturalPersonUserReference'], str(second_employee.id))
        self.assertEqual(dmfa_with_all_employees_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson'][1]['WorkerRecord']['Occupation']['OccupationUserReference'], str(second_employee.version_id.id))
        self._assertDMFAEqual(dmfa_with_all_employees_dict)
        ded3000 = self._get_ded3000(first_employee, payslips.filtered(lambda p: p.employee_id == first_employee))
        self.assertIn(145.92, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")
        ded3000 = self._get_ded3000(second_employee, payslips.filtered(lambda p: p.employee_id == second_employee))
        self.assertIn(0, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

        removed_payslip = payslips.filtered(lambda p: p.employee_id.name == 'Employee 2')
        dmfa.payslip_ids = [(3, removed_payslip.id)]
        removed_payslip.l10n_be_is_dmfa_reported = True
        with self.fake_time_object():
            dmfa.with_context(dmfa_skip_signature=True).generate_declaration_xml_report()
        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.state, 'ready')
        dmfa_with_filtered_employees_dict = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_with_filtered_employees_dict['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_with_filtered_employees_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], str(first_employee.id))
        self.assertEqual(dmfa_with_filtered_employees_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], str(first_employee.version_id.id))
        self._assertDMFAEqual(dmfa_with_filtered_employees_dict)
        ded3000 = self._get_ded3000(first_employee, payslips.filtered(lambda p: p.employee_id == first_employee))
        self.assertIn(145.92, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_dmfa_deduction_onssrestructuring_when_amount_zero(self):
        """ONSSRESTRUCTURING should be included when at least one line has amount > 0"""
        restructuring_employee = self.env['hr.employee'].create({
            'name': 'Employee 1',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'niss': '91111111192',
            'contract_date_start': datetime(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'birthday': datetime(2001, 1, 1),
            'restructuring_reduction_date_start': False,
            'wage': 2100,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        })
        payslip = self.env['hr.payslip'].create({
            'version_id': restructuring_employee.version_id.id,
            'date_from': datetime(2026, 1, 1),
            'date_to': datetime(2026, 1, 31),
            'employee_id': restructuring_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()
        restructuring_employee.write({'review_state': '1_reviewed'})
        payslip.action_payslip_done()

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TESTDMFA',
            'company_id': self.belgian_company.id,
            'year': '2026',
            'quarter': '1',
            'declaration_method': 'batch',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()
        dmfa_xml_response = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_xml_response['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_xml_response['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], f'{restructuring_employee.id}')
        self.assertEqual(dmfa_xml_response['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], f'{restructuring_employee.version_id.id}')
        self._assertDMFAEqual(dmfa_xml_response)
        ded3000 = self._get_ded3000(restructuring_employee, payslip)
        self.assertIn(497.38, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_dmfa_deduction_onssrestructuring_when_amount_positive(self):
        """ONSSRESTRUCTURING should be included when at least one line has amount > 0"""
        restructuring_employee = self.env['hr.employee'].create({
            'name': 'Employee 1',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'niss': '91111111192',
            'contract_date_start': datetime(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'birthday': datetime(2001, 1, 1),
            'restructuring_reduction_date_start': datetime(2026, 1, 1),
            'wage': 2100,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        })
        payslip = self.env['hr.payslip'].create({
            'version_id': restructuring_employee.version_id.id,
            'date_from': datetime(2026, 1, 1),
            'date_to': datetime(2026, 1, 31),
            'employee_id': restructuring_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        })
        payslip.compute_sheet()
        restructuring_employee.write({'review_state': '1_reviewed'})
        payslip.action_payslip_done()

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TESTDMFA',
            'company_id': self.belgian_company.id,
            'year': '2026',
            'quarter': '1',
            'declaration_method': 'batch',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()
        dmfa_xml_response = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_xml_response['DmfAOriginal']['@{http://www.w3.org/2001/XMLSchema-instance}noNamespaceSchemaLocation'], self._get_dmfa_original_xsd())
        self.assertEqual(dmfa_xml_response['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['NaturalPersonUserReference'], str(restructuring_employee.id))
        self.assertEqual(dmfa_xml_response['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationUserReference'], str(restructuring_employee.version_id.id))
        self._assertDMFAEqual(dmfa_xml_response)
        ded3000 = self._get_ded3000(restructuring_employee, payslip)
        self.assertIn(497.38, ded3000.values(), "Computing structural deduction using payslips results in a different amount than via dmfa services")

    @freeze_time("2025-04-10 10:00:00")
    def test_12_eco_friendly_vehicle(self):
        def _listify(value):
            return value if isinstance(value, list) else [value]

        def _check_remuneration_amount(person_dict, code, amount):
            remunerations = _listify(person_dict['WorkerRecord']['Occupation']['Remun'])
            if amount == '-1':
                self.assertFalse(any(r['RemunCode'] == code for r in remunerations))
            else:
                self.assertTrue(any(r['RemunCode'] == code and r['RemunAmount'] == amount for r in remunerations))

        def _check_contribution_amount(person_dict, code, amount):
            contributions = _listify(person_dict['WorkerRecord']['WorkerContribution'])
            if amount == '-1':
                self.assertFalse(any(c['ContributionWorkerCode'] == code for c in contributions))
            else:
                self.assertIn({'ContributionAmount': amount, 'ContributionType': '0', 'ContributionWorkerCode': code}, contributions)

        car_1 = self.car
        car_1.write({'co2': 110.0})

        brand_2 = self.env['fleet.vehicle.model.brand'].sudo().create({'name': "Another Brand"})
        model_2 = self.env['fleet.vehicle.model'].sudo().create({'name': "Another Model", 'brand_id': brand_2.id})
        car_2 = self.env['fleet.vehicle'].sudo().create({
            'name': "Eco Car",
            'license_plate': "Eco Car 1",
            'company_id': self.belgian_company.id,
            'model_id': model_2.id,
            'contract_date_start': date(2020, 10, 8),
            'co2': 0.0,
            'car_value': 38000.0,
            'fuel_type': "electric",
            'acquisition_date': date(2020, 1, 1)
        })

        car_3 = car_2.copy({'license_plate': "Eco Car 2"})

        employee_data = [
            ('Employee 1', '91111111192', car_1, False),
            ('Employee 2', '99010112390', car_2, False),
            ('Employee 3', '85010100115', car_3, True),
            ('Employee 4', '92022900306', False, True),
        ]
        employees = self.env['hr.employee'].create([
            {
                'name': name,
                'company_id': self.belgian_company.id,
                'country_id': self.env.ref('base.be').id,
                'niss': niss,
                'contract_date_start': datetime(2020, 1, 1),
                'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
                'work_contact_id': self.work_contact.copy().id,
                'wage': 3000,
                'car_id': car.id if car else False,
                'transport_mode_car': bool(car),
                'l10n_be_mobility_budget': mobility_budget,
                'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
                'lang': 'fr_BE',
            }
            for name, niss, car, mobility_budget in employee_data
        ])

        emp_2 = employees.filtered(lambda e: e.name == 'Employee 2')
        emp_3 = employees.filtered(lambda e: e.name == 'Employee 3')

        self.env['fleet.vehicle.assignation.log'].sudo().create([
            {
                'vehicle_id': car_2.id,
                'driver_id': emp_2.work_contact_id.id,
                'date_start': date(2025, 1, 1),
            },
            {
                'vehicle_id': car_3.id,
                'driver_id': emp_3.work_contact_id.id,
                'date_start': date(2025, 1, 1),
            },
        ])

        struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslips = self.env['hr.payslip'].create([
            {
                'name': f'Payslip Jan 2025 - {employee.name}',
                'version_id': employee.version_id.id,
                'date_from': datetime(2025, 1, 1),
                'date_to': datetime(2025, 1, 31),
                'employee_id': employee.id,
                'struct_id': struct.id,
                'company_id': self.belgian_company.id,
            }
            for employee in employees
        ])

        payslips.compute_sheet()
        employees.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        slips = payslips.filtered(lambda p: p.employee_id.name == 'Employee 1')
        line_co2_fee = slips.line_ids.filtered(lambda l: l.code == 'CO2FEE')
        self.assertAlmostEqual(line_co2_fee.total, 51.83, places=2)
        self.assertFalse(slips.line_ids.filtered(lambda l: l.code == 'ONSSEMPLOYER_868'))

        slips = payslips.filtered(lambda p: p.employee_id.name == 'Employee 2')
        line_co2_fee = slips.line_ids.filtered(lambda l: l.code == 'CO2FEE')
        self.assertAlmostEqual(line_co2_fee.total, 33.22, places=2)
        self.assertFalse(slips.line_ids.filtered(lambda l: l.code == 'ONSSEMPLOYER_868'))

        slips = payslips.filtered(lambda p: p.employee_id.name == 'Employee 3')
        self.assertFalse(slips.line_ids.filtered(lambda l: l.code == 'CO2FEE'))
        line_868 = slips.line_ids.filtered(lambda l: l.code == 'ONSSEMPLOYER_868')
        self.assertAlmostEqual(line_868.total, 33.22, places=2)

        slips = payslips.filtered(lambda p: p.employee_id.name == 'Employee 4')
        self.assertFalse(slips.line_ids.filtered(lambda l: l.code == 'CO2FEE'))
        self.assertFalse(slips.line_ids.filtered(lambda l: l.code == 'ONSSEMPLOYER_868'))

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TESTDMFA',
            'company_id': self.belgian_company.id,
            'year': '2025',
            'quarter': '1',
            'declaration_method': 'batch',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()
        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.state, 'ready')
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)

        # Company vehicle list:
        vehicles = _listify(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['CompanyVehicle'])
        self.assertTrue(any(v['LicensePlate'] == 'Eco Car 1' and v['EcoVehicle'] == '1' for v in vehicles))
        self.assertTrue(any(v['LicensePlate'] == 'Eco Car 2' and v['EcoVehicle'] == '1' for v in vehicles))
        self.assertTrue(any(v['LicensePlate'] == 'TEST' for v in vehicles))
        self.assertFalse(any(v['LicensePlate'] == 'TEST' and v.get('EcoVehicle') == '1' for v in vehicles))

        # CO2 Fee:
        common_contributions = _listify(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['ContributionUnrelatedToNP'])
        self.assertIn({'UnrelatedAmount': '00000032158', 'UnrelatedEmployerClass': '010', 'UnrelatedWorkerCode': '862'}, common_contributions)

        # Per employee: 1. Remuneration BIK car; 2. Contribution for eco-friendly car
        natural_persons = _listify(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson'])
        for person in natural_persons:
            if person.get('INSS') == '91111111192':
                # employee with diesel car
                _check_remuneration_amount(person, '010', '00000020526')
                _check_contribution_amount(person, '868', '-1')

            elif person.get('INSS') == '99010112390':
                # employee with electric car
                _check_remuneration_amount(person, '010', '00000014014')
                _check_contribution_amount(person, '868', '-1')

            elif person.get('INSS') == '85010100115':
                # employee with electric car and mobility budget
                _check_remuneration_amount(person, '010', '00000014014')
                _check_contribution_amount(person, '868', '00000003322')

            else:
                # employee with mobility budget and no car
                _check_remuneration_amount(person, '010', '-1')
                _check_contribution_amount(person, '868', '-1')

    @freeze_time("2025-04-10 10:00:00")
    def test_pool_cars_co2_contribution(self):
        def _listify(value):
            return value if isinstance(value, list) else [value]

        # Pool Car, No employee payslip assignment
        car_1 = self.env['fleet.vehicle'].sudo().create({
            'name': "Car 1",
            'license_plate': "CAR-001",
            'company_id': self.belgian_company.id,
            'model_id': self.model.id,
            'co2': 120.0,
            'fuel_type': "diesel",
            'acquisition_date': date(2024, 1, 1),
        })
        self.env['fleet.vehicle.assignation.log'].sudo().create({
            'vehicle_id': car_1.id,
            'driver_id': self.work_contact.id,
            'date_start': date(2025, 1, 1),
        })

        # Employee Car, Assigned Jan-Feb and returned as a pool car in March
        car_2 = self.env['fleet.vehicle'].sudo().create({
            'name': "Car 2",
            'license_plate': "CAR-002",
            'company_id': self.belgian_company.id,
            'model_id': self.model.id,
            'co2': 100.0,
            'fuel_type': "gasoline",
            'acquisition_date': date(2024, 1, 1),
        })
        self.env['fleet.vehicle.assignation.log'].sudo().create({
            'vehicle_id': car_2.id,
            'driver_id': self.work_contact.id,
            'date_start': date(2025, 1, 1),
        })

        # Pool Car, Acquired at Feb
        car_3 = self.env['fleet.vehicle'].sudo().create({
            'name': "Late Pool Car",
            'license_plate': "CAR-003",
            'company_id': self.belgian_company.id,
            'model_id': self.model.id,
            'co2': 110.0,
            'fuel_type': "diesel",
            'acquisition_date': date(2025, 2, 1),
        })
        self.env['fleet.vehicle.assignation.log'].sudo().create({
            'vehicle_id': car_3.id,
            'driver_id': self.work_contact.id,
            'date_start': date(2025, 2, 1),
        })

        # Employee assigned transition_car for Jan & Feb payslips
        self.employee.car_id = car_2.id

        struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslip_jan = self.env['hr.payslip'].create({
            'name': 'Payslip Jan 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': struct.id,
            'company_id': self.belgian_company.id,
            'vehicle_id': car_2.id,
        })

        payslip_feb = self.env['hr.payslip'].create({
            'name': 'Payslip Feb 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 2, 1),
            'date_to': datetime(2025, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': struct.id,
            'company_id': self.belgian_company.id,
            'vehicle_id': car_2.id,
        })

        payslip_mar = self.env['hr.payslip'].create({
            'name': 'Payslip Mar 2025',
            'version_id': self.contract.id,
            'date_from': datetime(2025, 3, 1),
            'date_to': datetime(2025, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': struct.id,
            'company_id': self.belgian_company.id,
            'vehicle_id': False,
        })

        payslips = payslip_jan + payslip_feb + payslip_mar
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        dmfa = self.env['l10n_be.dmfa'].with_user(self.payroll_manager).create({
            'name': 'TEST_POOL_CARS',
            'company_id': self.belgian_company.id,
            'year': '2025',
            'quarter': '1',
            'declaration_method': 'batch',
            'environment': 'S',
        })
        with self.fake_time_object():
            dmfa.with_context(onss_skip_signature=True).generate_declaration_xml_report()

        self.assertFalse(dmfa.error_message)
        self.assertEqual(dmfa.state, 'ready')

        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)

        vehicles = _listify(dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['CompanyVehicle'])
        plates = [v['LicensePlate'] for v in vehicles]

        self.assertEqual(len(vehicles), 4)
        self.assertIn('TEST', plates)
        self.assertIn('CAR-001', plates)
        self.assertIn('CAR-002', plates)
        self.assertIn('CAR-003', plates)

        # CO2 Fee Calculations Per Car (Greening Rules Applied - 2025):
        # -------------------------------------------------------------
        # TEST (Class Default Car):
        #   = 33.22
        # CAR-001 (Diesel, CO2=120):
        #   ((120 * 9 - 600) / 12) * (181.93 / 114.08) * 2.75 = 175.42
        #
        # CAR-002 (Gasoline, CO2=100):
        #   ((100 * 9 - 768) / 12) * (181.93 / 114.08) * 2.75 = 48.24
        #
        # CAR-003 (Diesel, CO2=110):
        #   ((110 * 9 - 600) / 12) * (181.93 / 114.08) * 2.75 = 142.53
        #

        # Total Vehicles Contribution Breakdown (Q1 2025):
        # ------------------------------------------------
        # 1. Payslips CO2 Fees:
        #    - CAR-002 on Employee Payslips (Jan & Feb): 48.24 * 2 = 96.48

        # 2. Pool Cars Monthly CO2 Fees (Jan, Feb, Mar):
        #    - January:
        #      * TEST:    33.22
        #      * CAR-001: 175.42
        #      Jan: 208.64
        #
        #    - February:
        #      * TEST:    33.22
        #      * CAR-001: 175.42
        #      * CAR-003: 142.53
        #      Feb: 351.17
        #
        #    - March:
        #      * TEST:    33.22
        #      * CAR-001: 175.42
        #      * CAR-002: 48.24
        #      * CAR-003: 142.53
        #      Mar: 399.41
        #
        # Total Vehicles Contribution: 96.48 "paid_payslips" + (208.64 + 351.17 + 399.41) "pool" = 1055.71

        self.assertEqual(dmfa._get_vehicles_contribution(), 1055.71)

    @freeze_time("2026-05-12 10:00:00")
    def test_100_dmfa_consultation_request_flow_invalid_noti(self):
        # Generate DmfA record
        self.belgian_company.onss_certificate_id = self.env['certificate.certificate'].create({})
        dmfa = self._generate_dmfa_declaration(environment='R', declaration_type='consultation', return_declaration=True, skip_signature=False)
        self.assertTrue(dmfa.xml_file)
        self.assertTrue(dmfa.xml_filename.startswith('FI.DMRQ.123456.20260512.'))
        self.assertTrue(dmfa.go_file)
        self.assertTrue(dmfa.go_filename.startswith('GO.DMRQ.123456.20260512.'))
        self.assertTrue(dmfa.signature_file)
        self.assertTrue(dmfa.signature_filename.startswith('FS.DMRQ.123456.20260512.'))
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_dict['DmfAConsultationRequest']['Form']['EmployerDeclarationId']['NaturalPerson']['NaturalPersonUserReference'], str(self.employee.id))
        self._assertDMFAEqual(dmfa_dict)

        # Generate DmfA SFTP declaration, valid ACRF, invalid NOTI
        dmfa.create_onss_declaration()
        declaration = dmfa.onss_declaration_ids
        self.assertEqual(dmfa.onss_declaration_count, 1)
        self.assertEqual(declaration.onss_file_count, 3)

        # Post DmfA SFTP declaration to ONSS
        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, ok
        def mock_listdir_declaration_3(folder):
            if folder == 'OUT':
                return [
                    'FO.ACRF.999999.20260512.00043.R',
                    'FS.ACRF.999999.20260512.00043.R',
                    'GO.ACRF.999999.20260512.00043.R',
                ]
            return []

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_4(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20260512.00043.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20261.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2026-05-12</FormCreationDate>
        <FormCreationHour>12:05:55.075</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>038055048FXXZ</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20260512.00043.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20260512.00043.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_3
            fake_sftp.file.side_effect = file_side_effect_declaration_4

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.ACRF.999999.20260512.00043.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.ACRF.999999.20260512.00043.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.ACRF.999999.20260512.00043.R', mode='rb')

        self.assertEqual(declaration.state, 'received')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 6)

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_2(folder):
            if folder in ('OUTTEST', 'OUTTEST-S'):
                return []
            elif folder == 'OUT':
                return [
                    'FO.NOTI.999999.20260512.00008.R',
                    'FS.NOTI.999999.20260512.00008.R',
                    'GO.NOTI.999999.20260512.00008.R',
                ]

        def file_side_effect_notification_2(remote_path, mode='rb'):
            dmfa_onss_file = declaration.onss_file_ids.filtered(lambda f: f.declaration_type == 'DMRQ' and f.file_type == 'FI')
            if remote_path.endswith('FO.NOTI.999999.20260512.00008.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?><NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="NOTIFICATION_20261.xsd">
<Form>
    <Identification>NOTI001</Identification>
    <FormCreationDate>2026-05-12</FormCreationDate>
    <FormCreationHour>10:03:05.124</FormCreationHour>
    <AttestationStatus>0</AttestationStatus>
    <TypeForm>FA</TypeForm>
    <HandledOriginalForm>
        <Identification>DMFAREQ</Identification>
          <FormCreationDate>%(form_creation_date)s</FormCreationDate>
          <FormCreationHour>%(form_creation_hour)s</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>RE</TypeForm>
    </HandledOriginalForm>
    <EmployerId>
        <NOSSRegistrationNbr>123456789</NOSSRegistrationNbr>
        <CompanyID>0123456789</CompanyID>
        </EmployerId>
        <ConcernedQuarter>
            <Quarter>20262</Quarter>
        </ConcernedQuarter>
        <HandledReference>
            <ReferenceType>1</ReferenceType>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>034090QVTP68Z</ReferenceNbr>
        </HandledReference>
        <HandlingResult>
            <ResultCode>0</ResultCode>
            <Diagnosis>3</Diagnosis>
            <AnomalyReport>
                <ErrorID>00013-008</ErrorID>
                <AnomalyClass>B</AnomalyClass>
                <AnomalyLabel>ANNÉE - TRIMESTRE - Pas dans le domaine de définition</AnomalyLabel>
                <Path>
                    <Quarter>20262</Quarter>
                    <NOSSRegistrationNbr>123456789</NOSSRegistrationNbr>
                    <Trusteeship>0</Trusteeship>
                    <CompanyID>0123456789</CompanyID>
                </Path>
            </AnomalyReport>
        </HandlingResult></Form>
</NOTIFICATION>""" % {'form_creation_date': dmfa_onss_file.form_creation_date, 'form_creation_hour': dmfa_onss_file.form_creation_hour}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.NOTI.999999.20260512.00008.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.NOTI.999999.20260512.00008.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_2
            fake_sftp.file.side_effect = file_side_effect_notification_2

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.NOTI.999999.20260512.00008.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.NOTI.999999.20260512.00008.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.NOTI.999999.20260512.00008.R', mode='rb')

        self.assertEqual(declaration.state, 'error')
        self.assertEqual(declaration.error_message, 'Declaration rejected - blocking anomalies\nAnomaly (1/1) - Code: 00013-008\nNot within scope\n- NISS: False\n- Anomaly Class: Blocking anomaly\n\n')
        self.assertEqual(declaration.onss_file_count, 9)

    @freeze_time("2026-05-12 10:00:00")
    def test_101_dmfa_consultation_request_flow_valid_dmdb(self):
        # Generate DmfA record
        self.belgian_company.onss_certificate_id = self.env['certificate.certificate'].create({})
        dmfa = self._generate_dmfa_declaration(environment='R', declaration_type='consultation', return_declaration=True, skip_signature=False)
        self.assertTrue(dmfa.xml_file)
        self.assertTrue(dmfa.xml_filename.startswith('FI.DMRQ.123456.20260512.'))
        self.assertTrue(dmfa.go_file)
        self.assertTrue(dmfa.go_filename.startswith('GO.DMRQ.123456.20260512.'))
        self.assertTrue(dmfa.signature_file)
        self.assertTrue(dmfa.signature_filename.startswith('FS.DMRQ.123456.20260512.'))
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        self.assertEqual(dmfa_dict['DmfAConsultationRequest']['Form']['EmployerDeclarationId']['NaturalPerson']['NaturalPersonUserReference'], str(self.employee.id))
        self._assertDMFAEqual(dmfa_dict)

        # Generate DmfA SFTP declaration, valid ACRF, invalid NOTI
        dmfa.create_onss_declaration()
        declaration = dmfa.onss_declaration_ids
        self.assertEqual(dmfa.onss_declaration_count, 1)
        self.assertEqual(declaration.onss_file_count, 3)

        # Post DmfA SFTP declaration to ONSS
        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, ok
        def mock_listdir_declaration_3(folder):
            if folder == 'OUT':
                return [
                    'FO.ACRF.999999.20260512.05142.R',
                    'FS.ACRF.999999.20260512.05142.R',
                    'GO.ACRF.999999.20260512.05142.R',
                ]
            return []

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_4(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20260512.05142.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20261.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2026-05-12</FormCreationDate>
        <FormCreationHour>12:05:55.075</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>038055048FXXZ</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20260512.05142.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20260512.05142.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_3
            fake_sftp.file.side_effect = file_side_effect_declaration_4

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.ACRF.999999.20260512.05142.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.ACRF.999999.20260512.05142.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.ACRF.999999.20260512.05142.R', mode='rb')

        self.assertEqual(declaration.state, 'received')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 6)

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_2(folder):
            if folder in ('OUTTEST', 'OUTTEST-S'):
                return []
            elif folder == 'OUT':
                return [
                    'FO.DMDB.999999.20260512.00089.R',
                    'FS.DMDB.999999.20260512.00089.R',
                    'GO.DMDB.999999.20260512.00089.R',
                ]

        def file_side_effect_notification_2(remote_path, mode='rb'):
            dmfa_onss_file = declaration.onss_file_ids.filtered(lambda f: f.declaration_type == 'DMRQ' and f.file_type == 'FI')
            if remote_path.endswith('FO.DMDB.999999.20260512.00089.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?><DmfAConsultationAnswer xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="DmfAConsultationAnswer_20261.xsd">
<Form>
    <Identification>DMFADB</Identification>
    <FormCreationDate>2026-05-12</FormCreationDate>
    <FormCreationHour>11:30:05.900</FormCreationHour>
    <AttestationStatus>0</AttestationStatus>
    <TypeForm>FA</TypeForm>
    <HandledOriginalForm>
        <Identification>DMFAREQ</Identification>
        <FormCreationDate>%(form_creation_date)s</FormCreationDate>
        <FormCreationHour>%(form_creation_hour)s</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>RE</TypeForm>
    </HandledOriginalForm>
    <HandledReference>
        <ReferenceType>1</ReferenceType>
        <ReferenceOrigin>2</ReferenceOrigin>
        <ReferenceNbr>034090RQSZY1Z</ReferenceNbr>
    </HandledReference>
    <EmployerDeclarationConsult>
        <Quarter>20261</Quarter>
        <NOSSRegistrationNbr>123456789</NOSSRegistrationNbr>
        <Trusteeship>0</Trusteeship>
        <CompanyID>0123456789</CompanyID>
        <System5>0</System5>
        <EmployerDeclarationPID>09199674454</EmployerDeclarationPID>
        <EmployerDeclarationVersionNbr>09310425029</EmployerDeclarationVersionNbr>
        <ResultCodeResearch>0</ResultCodeResearch>
        <NaturalPersonConsult>
            <NaturalPersonSequenceNbr>0000001</NaturalPersonSequenceNbr>
            <INSS>91111111192</INSS>
            <WorkerName>POIRET</WorkerName>
            <WorkerFirstName>LAURIE</WorkerFirstName>
            <NaturalPersonUserReference>5936591             </NaturalPersonUserReference>
            <NaturalPersonPID>00010908994</NaturalPersonPID>
            <DeclNaturalPersonPID>09199693297</DeclNaturalPersonPID>
            <DeclNaturalPersonVersionNbr>09199693297</DeclNaturalPersonVersionNbr>
            <ResultCodeResearch>0</ResultCodeResearch>
            <WorkerRecordConsult>
                <EmployerClass>010</EmployerClass>
                <WorkerCode>495</WorkerCode>
                <NOSSQuarterStartingDate>2026-01-01</NOSSQuarterStartingDate>
                <NOSSQuarterEndingDate>2026-03-31</NOSSQuarterEndingDate>
                <Border>0</Border>
                <WorkerRecordPID>09199693298</WorkerRecordPID>
                <WorkerRecordVersionNbr>09199693298</WorkerRecordVersionNbr>
                <CodeSubjected>0</CodeSubjected>
                <Action>2</Action>
                <OccupationConsultation>
                    <OccupationSequenceNbr>01</OccupationSequenceNbr>
                    <OccupationStartingDate>2025-11-03</OccupationStartingDate>
                    <JointCommissionNbr>200</JointCommissionNbr>
                    <WorkingDaysSystem>500</WorkingDaysSystem>
                    <ContractType>0</ContractType>
                    <RefMeanWorkingHours>3800</RefMeanWorkingHours>
                    <MeanWorkingHours>3800</MeanWorkingHours>
                    <Retired>0</Retired>
                    <OccupationUserReference>3300666</OccupationUserReference>
                    <OccupationVersionNbr>09199693299</OccupationVersionNbr>
                    <Action>2</Action>
                    <LocalUnitID>2131430983</LocalUnitID>
                    <ServiceAction>
                        <ServiceSequenceNbr>01</ServiceSequenceNbr>
                        <ServiceCode>001</ServiceCode>
                        <ServiceNbrDays>06400</ServiceNbrDays>
                        <ServiceNbrHours>0048640</ServiceNbrHours>
                        <Action>2</Action>
                    </ServiceAction>
                    <RemunAction>
                        <RemunSequenceNbr>01</RemunSequenceNbr>
                        <RemunCode>001</RemunCode>
                        <RemunAmount>00000838002</RemunAmount>
                        <Action>2</Action>
                    </RemunAction>
                    <RemunAction>
                        <RemunSequenceNbr>02</RemunSequenceNbr>
                        <RemunCode>010</RemunCode>
                        <RemunAmount>00000045754</RemunAmount>
                        <Action>2</Action>
                    </RemunAction>
                    <OccupationDeductionAction>
                        <DeductionCode>3000</DeductionCode>
                        <DeductionAmount>00000055747</DeductionAmount>
                        <Action>2</Action>
                    </OccupationDeductionAction>
                </OccupationConsultation>
                <WorkerContributionAction>
                    <ContributionWorkerCode>255</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000000168</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>256</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000000084</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>495</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000319027</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>809</ContributionWorkerCode>
                    <ContributionType>5</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000003268</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>810</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000000838</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>831</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000001927</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>855</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000014162</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>856</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionAmount>00000005088</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerContributionAction>
                    <ContributionWorkerCode>859</ContributionWorkerCode>
                    <ContributionType>0</ContributionType>
                    <ContributionCalculationBasis>00000838002</ContributionCalculationBasis>
                    <ContributionAmount>00000000838</ContributionAmount>
                    <Action>2</Action>
                </WorkerContributionAction>
                <WorkerDeductionAction>
                    <DeductionCode>0001</DeductionCode>
                    <DeductionAmount>00000040134</DeductionAmount>
                    <Action>2</Action>
               </WorkerDeductionAction>
               </WorkerRecordConsult>
        </NaturalPersonConsult>
        <NaturalPersonConsult>
            <NaturalPersonSequenceNbr>0000001</NaturalPersonSequenceNbr>
            <INSS>91111111192</INSS>
            <NaturalPersonPID>00010861969</NaturalPersonPID>
            <ResultCodeResearch>3</ResultCodeResearch>
        </NaturalPersonConsult>
    </EmployerDeclarationConsult>
</Form></DmfAConsultationAnswer>
""" % {'form_creation_date': dmfa_onss_file.form_creation_date, 'form_creation_hour': dmfa_onss_file.form_creation_hour}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.DMDB.999999.20260512.00089.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.DMDB.999999.20260512.00089.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_2
            fake_sftp.file.side_effect = file_side_effect_notification_2
            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.DMDB.999999.20260512.00089.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.DMDB.999999.20260512.00089.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.DMDB.999999.20260512.00089.R', mode='rb')

        self.assertEqual(declaration.state, 'notified')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 9)

        quarter_start, quarter_end = date_utils.get_quarter(date(2026, 1, 1))
        state = self.env['l10n_be.dmfa.natural_person.state'].sudo().search([
            ('niss', 'in', [self.employee.niss]),
            ('quarter_start', '=', quarter_start),
            ('quarter_end', '=', quarter_end),
        ])

        self.assertEqual(state.occupation_version_map, {'3300666': '09199693299'})
        self.assertEqual(state.natural_person_pid, '00010908994')
        self.assertEqual(state.decl_natural_person_pid, '09199693297')
        self.assertEqual(state.version_number, '09199693297')
        self.assertEqual(state.worker_record_version_number, '09199693298')

        expected_dict = {'deductions': [{'code': '0001',
                                         'deduction_calculation_basis': None,
                                         'deduction_amount': '00000040134',
                                         'deduction_right_starting_date': None,
                                         'applicant_inss': None,
                                         'certificate_origin': None}],
                         'contributions': [{'worker_code': '255',
                                            'contribution_type': '0',
                                            'amount': '00000000168',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '256',
                                            'contribution_type': '0',
                                            'amount': '00000000084',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '495',
                                            'contribution_type': '0',
                                            'amount': '00000319027',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '809',
                                            'contribution_type': '5',
                                            'amount': '00000003268',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '810',
                                            'contribution_type': '0',
                                            'amount': '00000000838',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '831',
                                            'contribution_type': '0',
                                            'amount': '00000001927',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '855',
                                            'contribution_type': '0',
                                            'amount': '00000014162',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None},
                                           {'worker_code': '856',
                                            'contribution_type': '0',
                                            'amount': '00000005088',
                                            'calculation_basis': None,
                                            'first_hiring_date': None},
                                           {'worker_code': '859',
                                            'contribution_type': '0',
                                            'amount': '00000000838',
                                            'calculation_basis': '00000838002',
                                            'first_hiring_date': None}],
                         'occupations': [{'ActivityCode': None,
                                          'TenthOrTwelfth': None,
                                          'apprenticeship': None,
                                          'commission': '200',
                                          'is_parttime': '0',
                                          'days_per_week': '500',
                                          'employment_promotion': None,
                                          'flying_staff_class': None,
                                          'days_justification': None,
                                          'position_code': None,
                                          'ref_mean_working_hours': '3800',
                                          'remun_method': None,
                                          'date_start': '2025-11-03',
                                          'date_end': None,
                                          'retired': '0',
                                          'mean_working_hours': '3800',
                                          'contract_id': '3300666',
                                          'version_number': '09199693299',
                                          'remunerations': [{'sequence': '01',
                                                             'code': '001',
                                                             'frequency': None,
                                                             'amount': '00000838002',
                                                             'percentage_paid': None},
                                                            {'sequence': '02',
                                                             'code': '010',
                                                             'frequency': None,
                                                             'amount': '00000045754',
                                                             'percentage_paid': None}],
                                          'occupation_deductions': [{'deduction_code': '3000',
                                                                     'deduction_calculation_basis': None,
                                                                     'deduction_amount': '00000055747',
                                                                     'deduction_right_starting_date': None,
                                                                     'management_cost_nbr_months': None,
                                                                     'replaced_inss': None,
                                                                     'applicant_inss': None,
                                                                     'certificate_origin': None}]}],
                         'student_contributions': [],
                         'update_action': 9}
        self.assertDictEqual(state.worker_record_data, expected_dict)

    @freeze_time("2026-05-12 10:00:00")
    def test_120_dmfa_update_flow_invalid_noti(self):
        # First, create an original declaration
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2026 %s',
            'version_id': self.contract.id,
            'date_from': datetime(2026, 1, 1),
            'date_to': datetime(2026, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Feb 2026',
            'version_id': self.contract.id,
            'date_from': datetime(2026, 2, 1),
            'date_to': datetime(2026, 2, 28),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Mar 2026',
            'version_id': self.contract.id,
            'date_from': datetime(2026, 3, 1),
            'date_to': datetime(2026, 3, 31),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])
        payslips.compute_sheet()
        self.employee.write({'review_state': '1_reviewed'})
        payslips.action_payslip_done()

        # Generate DmfA record
        self.belgian_company.onss_certificate_id = self.env['certificate.certificate'].create({})
        dmfa = self._generate_dmfa_declaration(environment='R', return_declaration=True, skip_signature=False)
        self.assertTrue(dmfa.xml_file)
        self.assertTrue(dmfa.go_file)
        self.assertTrue(dmfa.signature_file)

        # Generate DmfA SFTP declaration, valid ACRF, valid NOTI
        dmfa.create_onss_declaration()
        declaration = dmfa.onss_declaration_ids
        self.assertEqual(dmfa.onss_declaration_count, 1)
        self.assertEqual(declaration.onss_file_count, 3)

        # Post DmfA SFTP declaration to ONSS
        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.putfo = MagicMock()
            # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
            mock_open_conn.return_value.__enter__.return_value = fake_sftp
            mock_open_conn.return_value.__exit__.return_value = None
            declaration.action_post()
            mock_open_conn.assert_called_once()
            fake_sftp.putfo.assert_called()

        self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, ok
        def mock_listdir_declaration_3(folder):
            if folder == 'OUT':
                return [
                    'FO.ACRF.999999.20260512.99997.R',
                    'FS.ACRF.999999.20260512.99997.R',
                    'GO.ACRF.999999.20260512.99997.R',
                ]
            return []

        def make_file_mock(return_bytes):
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = return_bytes
            return mock_file

        def file_side_effect_declaration_3(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20260512.99997.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20251.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2026-05-12</FormCreationDate>
        <FormCreationHour>12:05:55.075</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>03804UE9XCMQZ</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20260512.99997.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20260512.99997.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_3
            fake_sftp.file.side_effect = file_side_effect_declaration_3

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.ACRF.999999.20260512.99997.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.ACRF.999999.20260512.99997.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.ACRF.999999.20260512.99997.R', mode='rb')

        self.assertEqual(declaration.state, 'received')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 6)

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_2(folder):
            if folder in ('OUTTEST', 'OUTTEST-S'):
                return []
            elif folder == 'OUT':
                return [
                    'FO.NOTI.999999.20260512.99997.R',
                    'FS.NOTI.999999.20260512.99997.R',
                    'GO.NOTI.999999.20260512.99997.R',
                ]

        def file_side_effect_notification_2(remote_path, mode='rb'):
            dmfa_onss_file = declaration.onss_file_ids.filtered(lambda f: f.declaration_type == 'DMFA' and f.file_type == 'FI')
            if remote_path.endswith('FO.NOTI.999999.20260512.99997.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?><NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="NOTIFICATION_20251.xsd">
<Form>
    <Identification>NOTI001</Identification>
    <FormCreationDate>2026-05-12</FormCreationDate>
    <FormCreationHour>21:48:14.795</FormCreationHour>
    <AttestationStatus>0</AttestationStatus>
    <TypeForm>FA</TypeForm>
    <HandledOriginalForm>
      <Identification>DMFA</Identification>
      <FormCreationDate>%(form_creation_date)s</FormCreationDate>
      <FormCreationHour>%(form_creation_hour)s</FormCreationHour>
      <AttestationStatus>0</AttestationStatus>
      <TypeForm>SU</TypeForm>
    </HandledOriginalForm>
    <Reference>
      <ReferenceType>1</ReferenceType>
      <ReferenceOrigin>1</ReferenceOrigin>
      <ReferenceNbr>2025/1</ReferenceNbr>
    </Reference>
<EmployerId>
      <NOSSRegistrationNbr>123456789</NOSSRegistrationNbr>
      <CompanyID>0123456789</CompanyID>
    </EmployerId>
    <ConcernedQuarter>
      <Quarter>20251</Quarter>
    </ConcernedQuarter>
<HandledReference>
      <ReferenceType>1</ReferenceType>
      <ReferenceOrigin>2</ReferenceOrigin>
      <ReferenceNbr>034081YBAQWPZ</ReferenceNbr>
    </HandledReference>
    <DeclarationComplInformations>
      <DMFAWorkersNbr>1</DMFAWorkersNbr>
      <DIMONAWorkersNbr>1</DIMONAWorkersNbr>
    </DeclarationComplInformations>
    <HandlingResult>
      <ResultCode>1</ResultCode>
    </HandlingResult>
  </Form>
</NOTIFICATION>""" % {'form_creation_date': dmfa_onss_file.form_creation_date, 'form_creation_hour': dmfa_onss_file.form_creation_hour}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.NOTI.999999.20260512.99997.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.NOTI.999999.20260512.99997.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_2
            fake_sftp.file.side_effect = file_side_effect_notification_2

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.NOTI.999999.20260512.99997.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.NOTI.999999.20260512.99997.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.NOTI.999999.20260512.99997.R', mode='rb')

        self.assertEqual(declaration.state, 'notified')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 9)

        # Second, receive DMPI file

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_3(folder):
            if folder in ('OUTTEST', 'OUTTEST-S'):
                return []
            elif folder == 'OUT':
                return [
                    'FO.DMPI.999999.20260512.04481.R.1.1',
                ]

        def file_side_effect_notification_3(remote_path, mode='rb'):
            if remote_path.endswith('FO.DMPI.999999.20260512.04481.R.1.1'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<DmfAPID xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="DmfAPID_20261.xsd">
   <Form>
      <Identification>DMFAPID</Identification>
      <FormCreationDate>2026-04-10</FormCreationDate>
      <FormCreationHour>20:00:19.000</FormCreationHour>
      <AttestationStatus>0</AttestationStatus>
      <TypeForm>SU</TypeForm>
      <Reference>
         <ReferenceType>3</ReferenceType>
         <ReferenceOrigin>2</ReferenceOrigin>
         <ReferenceNbr>03408XUJ0JUXZ</ReferenceNbr>
      </Reference>
      <Reference>
         <ReferenceType>3</ReferenceType>
         <ReferenceOrigin>1</ReferenceOrigin>
         <ReferenceNbr>%(original_reference)s</ReferenceNbr>
      </Reference>
      <Reference>
         <ReferenceType>1</ReferenceType>
         <ReferenceOrigin>2</ReferenceOrigin>
         <ReferenceNbr>03408XXN9L6DZ</ReferenceNbr>
      </Reference>
      <IDEmployerDeclaration>
         <Quarter>20251</Quarter>
         <NOSSRegistrationNbr>130387593</NOSSRegistrationNbr>
         <Trusteeship>0</Trusteeship>
         <CompanyID>477472701</CompanyID>
         <EmployerDeclarationPID>9199674454</EmployerDeclarationPID>
         <IDNaturalPerson>
            <INSS>91111111192</INSS>
            <NaturalPersonUserReference>3796105</NaturalPersonUserReference>
            <NaturalPersonPID>7786615</NaturalPersonPID>
            <DeclNaturalPersonPID>9199674455</DeclNaturalPersonPID>
            <DeclNaturalPersonVersionNbr>9199674455</DeclNaturalPersonVersionNbr>
            <IDWorkerRecord>
               <EmployerClass>010</EmployerClass>
               <WorkerCode>495</WorkerCode>
               <WorkerRecordVersionNbr>9199674456</WorkerRecordVersionNbr>
               <IDOccupation>
                  <OccupationSequenceNbr>1</OccupationSequenceNbr>
                  <OccupationVersionNbr>9199674457</OccupationVersionNbr>
                  <OccupationUserReference>5263452</OccupationUserReference>
               </IDOccupation>
            </IDWorkerRecord>
         </IDNaturalPerson>
        <IDNaturalPerson>
            <INSS>91111111291</INSS>
            <NaturalPersonUserReference>3796106</NaturalPersonUserReference>
            <NaturalPersonPID>7786616</NaturalPersonPID>
            <DeclNaturalPersonPID>9199674456</DeclNaturalPersonPID>
            <DeclNaturalPersonVersionNbr>9199674456</DeclNaturalPersonVersionNbr>
            <IDWorkerRecord>
               <EmployerClass>010</EmployerClass>
               <WorkerCode>495</WorkerCode>
               <WorkerRecordVersionNbr>9199674457</WorkerRecordVersionNbr>
               <IDOccupation>
                  <OccupationSequenceNbr>1</OccupationSequenceNbr>
                  <OccupationVersionNbr>9199674458</OccupationVersionNbr>
                  <OccupationUserReference>5263453</OccupationUserReference>
               </IDOccupation>
            </IDWorkerRecord>
         </IDNaturalPerson>
         <IDContUnrelatedToNP>
            <UnrelatedEmployerClass>010</UnrelatedEmployerClass>
            <UnrelatedWorkerCode>862</UnrelatedWorkerCode>
            <ContUnrelatedToNPVersionNbr>9199700637</ContUnrelatedToNPVersionNbr>
         </IDContUnrelatedToNP>
         <IDContUnrelatedToNP>
            <UnrelatedEmployerClass>010</UnrelatedEmployerClass>
            <UnrelatedWorkerCode>870</UnrelatedWorkerCode>
            <ContUnrelatedToNPVersionNbr>9199700638</ContUnrelatedToNPVersionNbr>
         </IDContUnrelatedToNP>
         <IDContUnrelatedToNP>
            <UnrelatedEmployerClass>010</UnrelatedEmployerClass>
            <UnrelatedWorkerCode>861</UnrelatedWorkerCode>
            <ContUnrelatedToNPVersionNbr>0000000000</ContUnrelatedToNPVersionNbr>
         </IDContUnrelatedToNP>
         <CompanyVehicleID>
            <LicensePlate>1-HAC-866</LicensePlate>
            <CompanyVehicleVersionNbr>9199700813</CompanyVehicleVersionNbr>
         </CompanyVehicleID>
      </IDEmployerDeclaration>
   </Form>
</DmfAPID>
""" % {'original_reference': declaration.batch_declaration_id.name}
                return make_file_mock(xml_str.encode('utf-8'))
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_3
            fake_sftp.file.side_effect = file_side_effect_notification_3
            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            self.employee_2.active = True
            quarter_start, quarter_end = date_utils.get_quarter(date(2025, 1, 1))
            emp1_state = self.env['l10n_be.dmfa.natural_person.state'].sudo().create({
                'niss': self.employee.niss,
                'employee_id': self.employee.id,
                'quarter_start': quarter_start,
                'quarter_end': quarter_end,
            })
            declaration._fetch_files()
            emp2_state = self.env['l10n_be.dmfa.natural_person.state'].sudo().search([
                ('niss', 'in', [self.employee_2.niss]),
                ('quarter_start', '=', quarter_start),
                ('quarter_end', '=', quarter_end),
            ])

            self.assertEqual(dmfa.company_pid, '09199674454')

            self.assertEqual(emp1_state.natural_person_pid, '7786615')
            self.assertEqual(emp1_state.decl_natural_person_pid, '9199674455')
            self.assertEqual(emp1_state.version_number, '9199674455')
            self.assertEqual(emp1_state.worker_record_version_number, '9199674456')

            emp2_state = self.env['l10n_be.dmfa.natural_person.state'].sudo().search([
                ('niss', 'in', [self.employee_2.niss]),
                ('quarter_start', '=', quarter_start),
                ('quarter_end', '=', quarter_end),
            ])

            self.assertEqual(emp2_state.natural_person_pid, '7786616')
            self.assertEqual(emp2_state.decl_natural_person_pid, '9199674456')
            self.assertEqual(emp2_state.version_number, '9199674456')
            self.assertEqual(emp2_state.worker_record_version_number, '9199674457')

            assert fake_sftp.file.call_count == 1
            fake_sftp.file.assert_any_call('OUT/FO.DMPI.999999.20260512.04481.R.1.1', mode='rb')

        # Last, generate DMFA update record
        with freeze_time("2026-05-12 12:00:00"):
            # Generate DmfA record
            self.belgian_company.onss_certificate_id = self.env['certificate.certificate'].create({})
            dmfa = self._generate_dmfa_declaration(environment='R', declaration_type='modification', return_declaration=True, skip_signature=False, parent=declaration.batch_declaration_id)
            self.assertTrue(dmfa.xml_file)
            self.assertTrue(dmfa.xml_filename.startswith('FI.DMWA.123456.20260512.'))
            self.assertTrue(dmfa.go_file)
            self.assertTrue(dmfa.go_filename.startswith('GO.DMWA.123456.20260512.'))
            self.assertTrue(dmfa.signature_file)
            self.assertTrue(dmfa.signature_filename.startswith('FS.DMWA.123456.20260512.'))
            dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
            self._assertDMFAEqual(dmfa_dict)

            # Generate DmfA SFTP declaration, valid ACRF, invalid NOTI
            dmfa.create_onss_declaration()
            declaration = dmfa.onss_declaration_ids
            self.assertEqual(dmfa.onss_declaration_count, 1)
            self.assertEqual(declaration.onss_file_count, 3)

            # Post DmfA SFTP declaration to ONSS
            with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
                fake_sftp = MagicMock()
                fake_sftp.putfo = MagicMock()
                # This mock needs to simulate the context manager behavior, specifically the __enter__ and __exit__ methods
                mock_open_conn.return_value.__enter__.return_value = fake_sftp
                mock_open_conn.return_value.__exit__.return_value = None
                declaration.action_post()
                mock_open_conn.assert_called_once()
                fake_sftp.putfo.assert_called()

            self.assertEqual(declaration.state, 'posted')

        # Receive ACRF, ok
        def mock_listdir_declaration_4(folder):
            if folder == 'OUT':
                return [
                    'FO.ACRF.999999.20260512.00071.R',
                    'FS.ACRF.999999.20260512.00071.R',
                    'GO.ACRF.999999.20260512.00071.R',
                ]
            return []

        def file_side_effect_declaration_4(remote_path, mode='rb'):
            if remote_path.endswith('FO.ACRF.999999.20260512.00071.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?>
<ACRF xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="ACRF_20261.xsd">
    <Form>
        <Identification>ACRF001</Identification>
        <FormCreationDate>2026-05-12</FormCreationDate>
        <FormCreationHour>12:05:55.075</FormCreationHour>
        <AttestationStatus>0</AttestationStatus>
        <TypeForm>FA</TypeForm>
        <FileReference>
            <FileName>%(go_filename)s</FileName>
            <ReferenceOrigin>2</ReferenceOrigin>
            <ReferenceNbr>038055048FXXZ</ReferenceNbr>
        </FileReference>
        <ReceptionResult>
            <ResultCode>1</ResultCode>
        </ReceptionResult>
    </Form>
</ACRF>""" % {'go_filename': dmfa.go_filename}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.ACRF.999999.20260512.00071.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.ACRF.999999.20260512.00071.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_declaration_4
            fake_sftp.file.side_effect = file_side_effect_declaration_4

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.ACRF.999999.20260512.00071.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.ACRF.999999.20260512.00071.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.ACRF.999999.20260512.00071.R', mode='rb')

        self.assertEqual(declaration.state, 'received')
        self.assertFalse(declaration.error_message)
        self.assertEqual(declaration.onss_file_count, 6)

        # Receive Notification, signaling an invalid declaration (blocking anomaly)
        def mock_listdir_notification_4(folder):
            if folder in ('OUTTEST', 'OUTTEST-S'):
                return []
            elif folder == 'OUT':
                return [
                    'FO.NOTI.999999.20260512.00034.R',
                    'FS.NOTI.999999.20260512.00034.R',
                    'GO.NOTI.999999.20260512.00034.R',
                ]

        def file_side_effect_notification_4(remote_path, mode='rb'):
            dmfa_onss_file = declaration.onss_file_ids.filtered(lambda f: f.declaration_type == 'DMWA' and f.file_type == 'FI')
            if remote_path.endswith('FO.NOTI.999999.20260512.00034.R'):
                xml_str = """<?xml version="1.0" encoding="UTF-8"?><NOTIFICATION xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="NOTIFICATION_20261.xsd">
<Form>
    <Identification>NOTI001</Identification>
    <FormCreationDate>2026-05-12</FormCreationDate>
    <FormCreationHour>12:39:21.812</FormCreationHour>
    <AttestationStatus>0</AttestationStatus>
    <TypeForm>FA</TypeForm>
    <HandledOriginalForm>
        <Identification>DMFAUPD</Identification>
        <FormCreationDate>%(form_creation_date)s</FormCreationDate>
        <FormCreationHour>%(form_creation_hour)s</FormCreationHour>
        <AttestationStatus>1</AttestationStatus>
        <TypeForm>SU</TypeForm>
    </HandledOriginalForm>
    <Reference>
        <ReferenceType>1</ReferenceType>
        <ReferenceOrigin>1</ReferenceOrigin>
        <ReferenceNbr>%(original_reference)s</ReferenceNbr>
    </Reference>
    <EmployerId>
        <NOSSRegistrationNbr>130387593</NOSSRegistrationNbr>
        <CompanyID>477472701</CompanyID>
    </EmployerId>
    <ConcernedQuarter>
        <Quarter>20261</Quarter>
    </ConcernedQuarter>
    <HandledReference>
        <ReferenceType>1</ReferenceType>
        <ReferenceOrigin>2</ReferenceOrigin>
        <ReferenceNbr>034090RTM7L9Z</ReferenceNbr>
    </HandledReference>
    <HandlingResult>
        <ResultCode>0</ResultCode>
        <Diagnosis>3</Diagnosis>
        <AnomalyReport>
        <ErrorID>00534-182</ErrorID>
        <AnomalyClass>B</AnomalyClass>
        <AnomalyLabel>IDENTIFIANT PERMANENT DE LA DÉCLARATION EMPLOYEUR - Non trouvé en DB DmfA</AnomalyLabel>
        <Path>
            <Quarter>20261</Quarter>
            <NOSSRegistrationNbr>130387593</NOSSRegistrationNbr>
            <Trusteeship>0</Trusteeship>
            <CompanyID>477472701</CompanyID>
        </Path>
        </AnomalyReport>
    </HandlingResult>
</Form>
</NOTIFICATION>
""" % {'form_creation_date': dmfa_onss_file.form_creation_date, 'form_creation_hour': dmfa_onss_file.form_creation_hour, 'original_reference': declaration.batch_declaration_id.name}
                return make_file_mock(xml_str.encode('utf-8'))
            if remote_path.endswith('FS.NOTI.999999.20260512.00034.R'):
                return make_file_mock(b"dummy\r\nsignature\r\n")
            if remote_path.endswith('GO.NOTI.999999.20260512.00034.R'):
                return make_file_mock(b"")
            raise FileNotFoundError(f"No mock for file: {remote_path}")

        with patch('odoo.addons.l10n_be_hr_payroll.models.l10n_be_onss_declaration.open_sftp_connection') as mock_open_conn:
            fake_sftp = MagicMock()
            fake_sftp.listdir.side_effect = mock_listdir_notification_4
            fake_sftp.file.side_effect = file_side_effect_notification_4

            mock_open_conn.return_value.__enter__.return_value = fake_sftp

            declaration._fetch_files()

            assert fake_sftp.file.call_count == 3
            fake_sftp.file.assert_any_call('OUT/FO.NOTI.999999.20260512.00034.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/FS.NOTI.999999.20260512.00034.R', mode='rb')
            fake_sftp.file.assert_any_call('OUT/GO.NOTI.999999.20260512.00034.R', mode='rb')

        self.assertEqual(declaration.state, 'error')
        self.assertEqual(declaration.error_message, 'Declaration rejected - blocking anomalies\nAnomaly (1/1) - Code: 00534-182\nNot found in DmfA database\n- NISS: False\n- Anomaly Class: Blocking anomaly\n\n')
        self.assertEqual(declaration.onss_file_count, 9)

    @freeze_time("2026-04-01 10:00:00")
    def test_artist_reduction_dmfa(self):
        artist_worker_code = self.env['l10n.be.worker.code'].search([('dmfa_code', '=', '046')])
        artist_employee = self.env['hr.employee'].create({
            'name': 'Artist Employee',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'address_id': self.partner_wallonia.id,
            'l10n_be_worker_code_id': artist_worker_code.id,
            'niss': '85010100115',
            'contract_date_start': datetime(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'wage': 5000,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Apr 2026',
            'version_id': artist_employee.version_id.id,
            'date_from': datetime(2026, 4, 1),
            'date_to': datetime(2026, 4, 30),
            'employee_id': artist_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip May 2026',
            'version_id': artist_employee.version_id.id,
            'date_from': datetime(2026, 5, 1),
            'date_to': datetime(2026, 5, 31),
            'employee_id': artist_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026',
            'version_id': artist_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': artist_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])

        payslips.compute_sheet()
        payslips.action_payslip_done()

        self._validate_payslip(payslips[0])

        dmfa = self._generate_dmfa_declaration(year=2026, quarter='2', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)

        # Testing 'l10n_be.dmfa.artist.reduction.line': Used solely for the
        # visibility of artist reductions on the payroll officer's DMFA tab.
        artist_line = dmfa.artist_reduction_line_ids.filtered(lambda l: l.employee_id == artist_employee)
        self.assertTrue(artist_line)
        self.assertEqual(artist_line.deduction_code, '4300')
        self.assertAlmostEqual(artist_line.amount, 517.0)

        # Testing the reduction on the dmfa itself
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertTrue(any(d == {'DeductionCode': '4300', 'DeductionAmount': '00000051700'} for d in occupation_deductions))

    @freeze_time("2026-04-01 10:00:00")
    def test_artist_reduction_dmfa_low_salary(self):
        artist_worker_code = self.env['l10n.be.worker.code'].search([('dmfa_code', '=', '046')])
        artist_employee = self.env['hr.employee'].create({
            'name': 'Artist Employee',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'address_id': self.partner_wallonia.id,
            'l10n_be_worker_code_id': artist_worker_code.id,
            'niss': '85010100115',
            'contract_date_start': datetime(2026, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'wage': 2000,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        })

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Apr 2026',
            'version_id': artist_employee.version_id.id,
            'date_from': datetime(2026, 4, 1),
            'date_to': datetime(2026, 4, 30),
            'employee_id': artist_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip May 2026',
            'version_id': artist_employee.version_id.id,
            'date_from': datetime(2026, 5, 1),
            'date_to': datetime(2026, 5, 31),
            'employee_id': artist_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026',
            'version_id': artist_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': artist_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }])

        payslips.compute_sheet()
        payslips.action_payslip_done()

        self._validate_payslip(payslips[0])

        dmfa = self._generate_dmfa_declaration(year=2026, quarter='2', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)

        # Testing the reduction on the dmfa itself
        occupation_deductions = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['OccupationDeduction']
        self.assertFalse(any(d['DeductionCode'] == '4300' for d in [occupation_deductions]))

    def test_bik_remuneration_code_without_working_days(self):

        def create_payslips_first_quarter():
            months = [(1, 31), (2, 28), (3, 31)]
            payslips = []
            for m, d in months:
                payslip = self.env['hr.payslip'].create({
                    'name': f'Payslip {datetime(2026, m, 1):%b %Y}',
                    'version_id': self.employee.version_id.id,
                    'date_from': datetime(2026, m, 1),
                    'date_to': datetime(2026, m, d),
                    'employee_id': self.employee.id,
                    'struct_id': struct.id,
                    'company_id': self.belgian_company.id,
                })
                payslip.compute_sheet()
                payslip.action_payslip_done()
                payslips.append(payslip)
            return payslips

        def get_bik_amount(payslip):
            bik_total = abs(payslip.line_ids.filtered(lambda line: line.code == 'ATN_DED').total)
            bik_car_total = abs(payslip.line_ids.filtered(lambda line: line.code == 'ATN.CAR').total)
            return bik_total - bik_car_total

        def get_remunerations(dmfa_dict):
            remunerations = (dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']['Remun'])
            return {
                remuneration['RemunCode']: int(remuneration['RemunAmount']) / 100
                for remuneration in remunerations
            }

        struct = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        employee_wage = self.employee.version_id.wage

        # Part 1: Without any absences
        payslips = create_payslips_first_quarter()
        dmfa = self._generate_dmfa_declaration(year='2026', quarter='1', return_declaration=True)
        remunerations = get_remunerations(xml_str_to_dict(dmfa.xml_file.content))

        bik_amount = 0
        for payslip in payslips:
            bik_amount += get_bik_amount(payslip)

        self.assertAlmostEqual(remunerations['001'], employee_wage * 3 + bik_amount, places=2)
        self.assertNotIn('002', remunerations)

        # Part 2: Sick Leave in January - March
        for slip in payslips:
            slip.action_payslip_cancel()
            slip.unlink()
        dmfa.unlink()

        sick_work_entry_type = self.env.ref('hr_work_entry.be_work_entry_type_sick_leave')
        self.env["hr.leave"].create({
            "name": "Long sick leave",
            "employee_id": self.employee.id,
            'work_entry_type_id': sick_work_entry_type.id,
            "request_date_from": date(2026, 1, 1),
            "request_date_to": date(2026, 3, 31),
        })
        payslips = create_payslips_first_quarter()
        dmfa_dict = self._generate_dmfa_declaration(year='2026', quarter='1')
        remunerations = get_remunerations(dmfa_dict)

        self.assertAlmostEqual(remunerations['001'], employee_wage, places=2)   # Only first 30 days of sick leave are paid
        self.assertAlmostEqual(remunerations['002'], bik_amount, places=2)

    @freeze_time("2026-07-01 10:00:00")
    def test_starterjob_reduction_dmfa(self):
        starterjob_employee, regular_employee, lower_wage_employee = self.env['hr.employee'].create([{
            'name': 'StarterJob Employee',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'address_id': self.partner_wallonia.id,
            'niss': '07020118374',
            'birthday': datetime(2007, 2, 1),
            'contract_date_start': datetime(2025, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'wage': 2500,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'l10n_be_is_starterjob': True,
            'lang': 'fr_BE',
        }, {
            'name': 'Regular Employee',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'address_id': self.partner_wallonia.id,
            'niss': '07020118572',
            'birthday': datetime(2007, 2, 1),
            'contract_date_start': datetime(2025, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'wage': 2500,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        }, {
            'name': 'Lowerwage Employee',
            'company_id': self.belgian_company.id,
            'country_id': self.env.ref('base.be').id,
            'address_id': self.partner_wallonia.id,
            'niss': '07020118473',
            'birthday': datetime(2007, 2, 1),
            'contract_date_start': datetime(2025, 1, 1),
            'structure_type_id': self.env.ref('hr.structure_type_employee_cp200').id,
            'work_contact_id': self.work_contact.id,
            'wage': 2200,
            'l10n_be_joint_committee_id': self.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            'lang': 'fr_BE',
        }])

        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip Jan 2025 - StarterJob Employee',
            'version_id': starterjob_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': starterjob_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026 - StarterJob Employee',
            'version_id': starterjob_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': starterjob_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026 - StarterJob Employee - Double Holiday',
            'version_id': starterjob_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': starterjob_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jan 2025 - Regular Employee',
            'version_id': regular_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': regular_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026 - Regular Employee',
            'version_id': regular_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': regular_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026 - Regular Employee - Double Holiday',
            'version_id': regular_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': regular_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jan 2025 - Lower wage Employee',
            'version_id': lower_wage_employee.version_id.id,
            'date_from': datetime(2025, 1, 1),
            'date_to': datetime(2025, 1, 31),
            'employee_id': lower_wage_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026 - Lower wage Employee',
            'version_id': lower_wage_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': lower_wage_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Payslip Jun 2026 - Lower wage Employee - Double Holiday',
            'version_id': lower_wage_employee.version_id.id,
            'date_from': datetime(2026, 6, 1),
            'date_to': datetime(2026, 6, 30),
            'employee_id': lower_wage_employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_double_holiday').id,
            'company_id': self.belgian_company.id,
        }])

        payslips.compute_sheet()
        payslips.action_payslip_done()
        regular_payslip = payslips.filtered(lambda p: p.employee_id == regular_employee)
        lower_wage_payslip = payslips.filtered(lambda p: p.employee_id == lower_wage_employee)
        starterjob_payslip = payslips - regular_payslip - lower_wage_payslip
        # This employee is 19 yo so with his starterjob status he will be pay 88% of his wage (2500 * 88% =) 2200
        self.assertAlmostEqual(regular_payslip[0].line_ids.filtered(lambda l: l.code == 'NET').total - lower_wage_payslip[0].line_ids.filtered(lambda l: l.code == 'NET').total, 57.01, 2, "should be equal to the COMPSUPP's value of the starterjob's payslip")
        self._validate_payslip(starterjob_payslip[0])

        self.assertAlmostEqual(regular_payslip[1].line_ids.filtered(lambda l: l.code == 'NET').total - lower_wage_payslip[1].line_ids.filtered(lambda l: l.code == 'NET').total, 51.61, 2, "should be equal to the COMPSUPP's value of the starterjob's payslip")
        self._validate_payslip(starterjob_payslip[1])

        # This employee is 19 yo so with his starterjob status he will be pay 88% of his Double holiday Pay DH_BASIC (= (DOUBLE + DOUBLE_COMPLEMENTARY) * 88%)
        self.assertAlmostEqual(regular_payslip[2].line_ids.filtered(lambda l: l.code == 'NET').total - lower_wage_payslip[2].line_ids.filtered(lambda l: l.code == 'NET').total, 105.44, 2, "should be equal to the COMPSUPP's value of the starterjob's payslip")
        self._validate_payslip(starterjob_payslip[2])

        dmfa = self._generate_dmfa_declaration(year=2026, quarter='2', return_declaration=True)
        dmfa_dict = xml_str_to_dict(dmfa.xml_file.content)
        # Testing the reduction on the dmfa itself for the starterjob's employee
        employee_occupation = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson'][0]['WorkerRecord']['Occupation']
        employment_promotion = employee_occupation['EmploymentPromotion']
        career_measure = employee_occupation['OccupationInformations']['CareerMeasure']
        self.assertEqual(employment_promotion, '10')
        self.assertEqual(career_measure, '2')

    @freeze_time("2026-04-10 10:00:00")
    def test_13_declaration_warrants(self):
        warrant_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_structure_warrant')
        regular_structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')

        self.contract.generate_work_entries(date(2026, 1, 1), date(2026, 1, 31))

        payslips = self.env['hr.payslip'].create([{
            'name': 'Regular Payslip',
            'version_id': self.contract.id,
            'date_from': datetime(2026, 1, 1),
            'date_to': datetime(2026, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': regular_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Warrant Without ONSS',
            'version_id': self.contract.id,
            'date_from': datetime(2026, 1, 1),
            'date_to': datetime(2026, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': warrant_structure.id,
            'company_id': self.belgian_company.id,
        }, {
            'name': 'Warrant With ONSS',
            'version_id': self.contract.id,
            'date_from': datetime(2026, 1, 1),
            'date_to': datetime(2026, 1, 31),
            'employee_id': self.employee.id,
            'struct_id': warrant_structure.id,
            'company_id': self.belgian_company.id,
        }])

        payslips[1]._set_input_value('WARRANT_WITHOUT_ONSS', 10000.00)
        payslips[2]._set_input_value('WARRANT_WITH_ONSS', 5000.00)

        self.employee.write({'review_state': '1_reviewed'})

        for payslip in payslips:
            payslip.compute_sheet()
            payslip.action_payslip_done()

        dmfa_dict = self._generate_dmfa_declaration(year='2026', quarter='1')

        self._assertDMFAEqual(dmfa_dict)

    @freeze_time("2026-04-10 10:00:00")
    def test_intellectual_property_remuneration_codes(self):
        # Since 2026, the intellectual property exempt from ONSS (within 30 % of the total
        # remuneration) is declared under the remuneration code 47 and excluded from the code 1
        self.contract.write({'ip_wage_rate': 0.25, 'ip_onss': False})  # 750 € on a 3000 € wage, exempt from ONSS
        payslips = self.env['hr.payslip'].create([{
            'name': 'Payslip %s 2026' % date_from.strftime('%B'),
            'version_id': self.contract.id,
            'date_from': date_from,
            'date_to': date_from + relativedelta(months=1, days=-1),
            'employee_id': self.employee.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'company_id': self.belgian_company.id,
        } for date_from in (date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1))])
        self.employee.write({'review_state': '1_reviewed'})
        for payslip in payslips:  # No batch compute and validate for ONSS regularization
            payslip.compute_sheet()
            payslip.action_payslip_done()
        line_values = payslips._get_line_values(['SALARY', 'IP.EXEMPT', 'IP'], compute_sum=True)
        self.assertAlmostEqual(line_values['IP.EXEMPT']['sum']['total'], -2250, 2)
        self.assertAlmostEqual(line_values['IP']['sum']['total'], 2250, 2)

        dmfa_dict = self._generate_dmfa_declaration(year='2026', quarter='1')
        natural_person = dmfa_dict['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']
        if isinstance(natural_person, list):
            natural_person = next(p for p in natural_person if p['NaturalPersonUserReference'] == str(self.employee.id))
        remunerations = natural_person['WorkerRecord']['Occupation']['Remun']
        if isinstance(remunerations, dict):
            remunerations = [remunerations]
        amounts_by_code = {remun['RemunCode']: int(remun['RemunAmount']) for remun in remunerations}
        self.assertEqual(amounts_by_code['047'], 225000)  # in cents
        self.assertEqual(amounts_by_code['001'], round(line_values['SALARY']['sum']['total'] * 100))

    def test_ded3000_while_computing_payslips(self):
        """
        Make sure that ONSS_STRUCTURAL (ded3000) is correctly computed while computing payslips
        using the localdict instead of the payslip lines (not yet populated),
        and that the value is the same in DMFA declaration.
        """
        date_from = date(2025, 1, 1)
        date_to = date(2025, 1, 31)
        payslip = self.env['hr.payslip'].create({
            'name': 'Payslip Jan 2025',
            'employee_id': self.employee.id,
            'version_id': self.employee.version_id.id,
            'struct_id': self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary').id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.belgian_company.id,
        })
        self.env['hr.leave'].create({
            'employee_id': self.employee.id,
            'request_date_from': date(2025, 1, 6),
            'request_date_to': date(2025, 1, 10),
            'work_entry_type_id': self.env.ref('hr_work_entry.be_work_entry_type_unpaid_leave').id,
        })
        payslip.compute_sheet()
        self.assertEqual(payslip.state, 'draft')
        ded3000_draft = - sum(payslip.line_ids.filtered(lambda line: line.code == 'ONSS_STRUCTURAL').mapped('total'))
        ded3000_draft_recomputed = self._get_ded3000(self.employee, payslip)
        self.assertIn(ded3000_draft, ded3000_draft_recomputed.values())

        payslip.action_payslip_done()
        self.assertEqual(payslip.state, 'validated')
        ded3000_validated = self._get_ded3000(self.employee, payslip)
        self.assertIn(ded3000_draft, ded3000_validated.values())

        dmfa = self._generate_dmfa_declaration(year=2025, quarter='1')
        occupations = dmfa['DmfAOriginal']['Form']['EmployerDeclaration']['NaturalPerson']['WorkerRecord']['Occupation']
        occupations = [occupations] if isinstance(occupations, dict) else occupations
        ded3000_dmfa = []
        for occupation in occupations:
            deductions = occupation.get('OccupationDeduction', [])
            deductions = [deductions] if isinstance(deductions, dict) else deductions
            ded3000_dmfa.extend([int(d.get('DeductionAmount')) / 100.0 for d in deductions if d.get('DeductionCode') == '3000'])
        self.assertIn(ded3000_draft, ded3000_dmfa)
