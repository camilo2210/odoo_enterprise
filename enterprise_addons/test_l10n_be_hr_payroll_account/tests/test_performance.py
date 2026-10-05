# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import time

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from odoo.tests.common import tagged, users, warmup
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_be_hr_payroll.tests.common import TestBelgiumCommon

_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'payroll_perf')
class TestPerformance(TestBelgiumCommon, AccountTestInvoicingCommon):

    @classmethod
    @AccountTestInvoicingCommon.setup_country('be')
    def setUpClass(cls):
        super().setUpClass()

        cls.EMPLOYEES_COUNT = 100

        cls.company_data['company'].write({
            'street': 'Rue du Paradis',
            'zip': '6870',
            'city': 'Eghezee',
            'vat': 'BE0897223670',
            'phone': '061928374',
        })
        cls.company_data['company'].sudo().current_payroll_config_id.write({
            'l10n_be_company_number': '0477472701',
            'l10n_be_revenue_code': '1293',
            'onss_importance_code': '1',
            'l10n_be_employer_category_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_employer_category_00010').id
        })

        admin = cls.env.ref('base.user_admin')
        admin.email = 'mitchell.admin@example.com'
        admin.company_ids |= cls.company

        cls.env.user.tz = 'Europe/Brussels'

        cls.date_from = date(2020, 9, 1)
        cls.date_to = date(2020, 9, 30)

        belgium = cls.env.ref('base.be')

        resource_calendar_38_hours_per_week = cls.env['resource.calendar'].sudo().create([{
            'name': "Test Calendar : 38 Hours/Week",
            'company_id': cls.company.id,
            'hours_per_day': 7.6,
            'hours_per_week': 38.0,
            'full_time_required_hours': 38.0,
            'attendance_ids': [(5, 0, 0)] + [(0, 0, {
                'dayofweek': dayofweek,
                'hour_from': hour_from,
                'hour_to': hour_to,
                'work_entry_type_id': cls.env.ref('hr_work_entry.be_work_entry_type_attendance').id

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

        # When exiting a query count assertion context, the registry is flushed,
        # to optimize that process, the ORM tries batches writes as necessary.
        # However, since we include the employee id/name in some of those templates,
        # this causes some instability during flushing every time we add a new digit.
        # (file size of pdf documents changes)
        # The following view ensures the same file size regardless of employee id (up to 12 digits)
        # and thus the same query count.
        template_id = cls.env.ref('l10n_be_hr_payroll.report_281_10').id
        cls.env['ir.ui.view'].create({
            'name': 'patch_report_281_10',
            'type': 'qweb',
            'inherit_id': template_id,
            'arch': """
                <xpath expr="//div[hasclass('page')]/div[hasclass('row')][2]/div[1]" position="replace">
                    <div class="col-4 border-end">
                        <strong>1. Nr.</strong> <span t-out="str(employee.id).zfill(12)"/>
                    </div>
                </xpath>
            """
        })
        cls.employees = cls.env['hr.employee'].sudo().create([{
            'name': f"Test Employee {i:03}",
            'private_street': 'Brussels Street',
            'private_city': 'Brussels',
            'private_zip': '2928',
            'private_country_id': belgium.id,
            'resource_calendar_id': resource_calendar_38_hours_per_week.id,
            'company_id': cls.company.id,
            'distance_home_work': 75,
            'niss': '93051822361',
            'review_state': '1_reviewed',
            'certificate': 'master',
            'lang': 'fr_BE',
        } for i in range(cls.EMPLOYEES_COUNT)]).sudo(False)

        brand = cls.env['fleet.vehicle.model.brand'].sudo().create([{
            'name': "Test Brand"
        }])

        model = cls.env['fleet.vehicle.model'].sudo().create([{
            'name': "Test Model",
            'brand_id': brand.id
        }])

        cls.cars = cls.env['fleet.vehicle'].sudo().create([{
            'name': f"Test Car {i}",
            'license_plate': f"TEST {i}",
            'driver_id': cls.employees[i].work_contact_id.id,
            'company_id': cls.company.id,
            'model_id': model.id,
            'contract_date_start': date(2020, 10, 8),
            'co2': 88.0,
            'car_value': 38000.0,
            'fuel_type': "diesel",
            'acquisition_date': date(2020, 1, 1)
        } for i in range(cls.EMPLOYEES_COUNT)]).sudo(False)

        cls.env['fleet.vehicle.log.contract'].sudo().create([{
            'name': f"Test Contract{i}",
            'vehicle_id': cls.cars[i].id,
            'company_id': cls.company.id,
            'start_date': date(2020, 10, 8),
            'expiration_date': date(2021, 10, 8),
            'state': "open",
            'cost_generated': 0.0,
            'cost_frequency': "monthly",
            'recurring_cost_amount_depreciated': 450.0
        } for i in range(cls.EMPLOYEES_COUNT)])

        for i, employee in enumerate(cls.employees.sudo()):
            employee.version_id.write({
                'resource_calendar_id': resource_calendar_38_hours_per_week.id,
                'company_id': cls.company.id,
                'car_id': cls.cars[i].id,
                'structure_type_id': cls.env.ref('hr.structure_type_employee_cp200').id,
                'contract_date_start': date(2018, 12, 31),
                'date_version': date(2018, 12, 31),
                'wage': 2400,
                'transport_mode_car': True,
                'fuel_card': 150.0,
                'internet': 38.0,
                'mobile': 30.0,
                'meal_voucher_amount': 7.45,
                'ip_wage_rate': 0.25,
                'rd_percentage': 1.0,
                'review_state': '1_reviewed',
                'l10n_be_joint_committee_id': cls.env.ref('l10n_be_hr_payroll.l10n_be_joint_committee_200').id,
            })
        cls.contracts = cls.employees.sudo().version_ids

        # Public Holiday (global)
        cls.env['resource.calendar.leaves'].sudo().create([{
            'name': "Public Holiday (global)",
            'calendar_id': resource_calendar_38_hours_per_week.id,
            'company_id': cls.company.id,
            'date_from': datetime(2020, 9, 22, 5, 0, 0),
            'date_to': datetime(2020, 9, 22, 23, 0, 0),
            'resource_id': False,
            'count_as': "absence",
            'work_entry_type_id': cls.env.ref('hr_work_entry.l10n_be_work_entry_type_bank_holiday').id
        }])

        # Everyone takes a legal leave the same day
        legal_leave = cls.env.ref('hr_work_entry.be_work_entry_type_legal_leave')
        cls.env['resource.calendar.leaves'].sudo().create([{
            'name': "Legal Leave %i" % i,
            'calendar_id': resource_calendar_38_hours_per_week.id,
            'company_id': cls.company.id,
            'resource_id': cls.employees[i].resource_id.id,
            'date_from': datetime(2020, 9, 14, 5, 0, 0),
            'date_to': datetime(2020, 9, 15, 23, 0, 0),
            'count_as': "absence",
            'work_entry_type_id': legal_leave.id,
        } for i in range(cls.EMPLOYEES_COUNT)])

    @users('admin')
    @warmup
    def test_performance_l10n_be_payroll_whole_flow(self):
        # Work entry generation
        with self.assertQueryCount(admin=1800):
            self.employees.sudo().generate_work_entries(self.date_from, self.date_to)

        structure = self.env.ref('l10n_be_hr_payroll.hr_payroll_structure_cp200_employee_salary')
        payslips_values = [{
            'name': "Test Payslip %i" % i,
            'employee_id': self.employees[i].id,
            'version_id': self.contracts[i].id,
            'company_id': self.company.id,
            'vehicle_id': self.cars[i].id,
            'struct_id': structure.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
        } for i in range(self.EMPLOYEES_COUNT)]

        # Payslip Creation
        with self.assertQueryCount(admin=6000):  # randomness
            start_time = time.time()
            payslips = self.env['hr.payslip'].with_context(allowed_company_ids=self.company.ids).create(payslips_values)
            # --- 0.3016078472137451 seconds ---
            _logger.info("Payslips Creation: --- %s seconds ---", time.time() - start_time)

        # Payslip Computation
        with self.assertQueryCount(admin=1215):
            start_time = time.time()
            payslips.compute_sheet()
            # --- 9.298089027404785 seconds ---
            _logger.info("Payslips Computation: --- %s seconds ---", time.time() - start_time)

        # Payslip Validation
        with self.assertQueryCount(admin=190):
            start_time = time.time()
            payslips.action_payslip_done()
            # --- 0.6920671463012695 seconds ---
            _logger.info("Payslips Validation: --- %s seconds ---", time.time() - start_time)

        # 273.XX Declaration
        declaration_273_xx = self.env['l10n_be.273_xx'].with_context(allowed_company_ids=self.company.ids).create({
            'year': self.date_from.year,
            'month': str(self.date_from.month),
        })
        with self.assertQueryCount(admin=17):
            start_time = time.time()
            declaration_273_xx._generate_xml()
            # --- 0.027051687240600586 seconds ---
            _logger.info("Declaration 273.xx: --- %s seconds ---", time.time() - start_time)
        self.assertEqual(declaration_273_xx.xml_validation_state, 'done')

        # # 274.XX Declaration
        # declaration_274_XX = self.env['l10n_be.274_xx'].with_context(allowed_company_ids=self.company.ids).create({
        #     'year': self.date_from.year,
        #     'month': str(self.date_from.month),
        # })
        # with self.assertQueryCount(admin=19):
        #     start_time = time.time()
        #     declaration_274_XX.action_generate_xml()
        #     # --- 0.04558062553405762 seconds ---
        #     _logger.info("Declaration 274.XX: --- %s seconds ---", time.time() - start_time)
        # self.assertEqual(declaration_274_XX.xml_validation_state, 'done', declaration_274_XX.error_message)

        # 281.xx Declaration
        declaration_281_xx = self.env['l10n_be.281_xx'].with_context(allowed_company_ids=self.company.ids).create({
            'year': str(self.date_from.year),
        })
        declaration_281_10 = declaration_281_xx.l10n_be_281_10_ids
        declaration_281_10.action_generate_declarations()
        declaration_281_45 = declaration_281_xx.l10n_be_281_45_ids
        declaration_281_45.action_generate_declarations()
        self.assertEqual(len(declaration_281_10.line_ids), self.EMPLOYEES_COUNT)
        self.assertEqual(len(declaration_281_45.line_ids), self.EMPLOYEES_COUNT)
        with self.assertQueryCount(admin=256):
            start_time = time.time()
            declaration_281_xx.action_generate_xml()
            # --- 0.22338032722473145 seconds ---
            _logger.info("Declaration 281.xx XML:--- %s seconds ---", time.time() - start_time)
        self.assertEqual(declaration_281_xx.state, 'ready', declaration_281_xx.error_message)

        with self.assertQueryCount(admin=2444):
            start_time = time.time()
            declaration_281_10.line_ids.write({
                'pdf_to_generate': True,
                'pdf_to_post': True,
            })
            self.env['hr.payslip']._cron_generate_pdf(batch_size=100)
            # --- X seconds ---
            _logger.info("Declaration 281.10 PDF:--- %s seconds ---", time.time() - start_time)

        with self.assertQueryCount(admin=2124):
            start_time = time.time()
            declaration_281_45.line_ids.write({
                'pdf_to_generate': True,
                'pdf_to_post': True,
            })
            self.env['hr.payslip']._cron_generate_pdf(batch_size=100)
            # --- X seconds ---
            _logger.info("Declaration 281.45 PDF:--- %s seconds ---", time.time() - start_time)

        # Individual Account Declaration
        individual_accounts = self.env['l10n_be.individual.account'].with_context(allowed_company_ids=self.company.ids).create({
            'year': str(self.date_from.year),
            'name': 'Test',
        })
        individual_accounts.action_generate_declarations()
        self.assertEqual(len(individual_accounts.line_ids), self.EMPLOYEES_COUNT)
        with self.assertQueryCount(admin=1621):
            start_time = time.time()
            individual_accounts.line_ids.write({
                'pdf_to_generate': True,
                'pdf_to_post': True,
            })
            self.env['hr.payslip']._cron_generate_pdf(batch_size=100)
            # --- X seconds ---
            _logger.info("Individual Accounts PDF:--- %s seconds ---", time.time() - start_time)

        # Social Security Certificate
        social_security_certificate = self.env['l10n.be.social.security.certificate'].with_context(allowed_company_ids=self.company.ids).create({
            'date_from': self.date_from + relativedelta(day=1, month=1),
            'date_to': self.date_from + relativedelta(day=31, month=12),
        })
        with self.assertQueryCount(admin=167):
            start_time = time.time()
            social_security_certificate.print_report()
            # --- 0.4724118709564209 seconds ---
            _logger.info("Social Security Certificate:--- %s seconds ---", time.time() - start_time)
