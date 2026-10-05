from odoo.addons.esg.tests.esg_common import TestEsgCommon


class TestEsgReport(TestEsgCommon):

    _test_user_groups = None  # FIXME list needed groups

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_type = cls.env.ref('hr.contract_type_employee')
        cls.department_1, cls.department_2, cls.department_3 = cls.env['hr.department'].sudo().create([
            {'name': 'Research & Development'},
            {'name': 'Marketing'},
            {'name': 'Sales'},
        ])
        cls.employees = cls.env['hr.employee'].sudo().create([
            {
                'name': 'Employee 0',
                'date_version': '1125-01-01',
                'contract_date_start': '1125-01-01',
                'contract_date_end': '1128-01-01',
                'employee_type_id': cls.employee_type.id,
                'sex': 'female',
                'birthday': '1090-03-01',
                'department_id': cls.department_1.id,
                'wage': 100.0,
            },
            {
                'name': 'Employee 1',
                'work_contact_id': cls.env.user.partner_id.id,
                'date_version': '1124-01-01',
                'contract_date_start': '1125-01-01',
                'employee_type_id': cls.employee_type.id,
                'sex': 'male',
                'birthday': '1100-08-15',
                'department_id': cls.department_2.id,
                'wage': 80.0,
            },
            {
                'name': 'Employee 2',
                'date_version': '1123-01-01',
                'employee_type_id': cls.employee_type.id,
                'sex': 'male',
                'birthday': '1072-06-12',
            },
            {
                'name': 'Employee 3',
                'date_version': '1123-01-01',
                'employee_type_id': cls.employee_type.id,
                'sex': 'female',
            },
            {
                'name': 'Employee 4',
                'date_version': '1105-01-01',
                'contract_date_start': '1105-01-01',
                'contract_date_end': '1108-01-01',
                'employee_type_id': cls.employee_type.id,
                'sex': 'male',
                'birthday': '1060-08-15',
                'department_id': cls.department_2.id,
                'wage': 60.0,
            },
            {
                'name': 'Non-Employee 0',
                'date_version': '1125-01-01',
                'contract_date_start': '1125-01-01',
                'contract_date_end': '1125-03-01',
                'employee_type_id': cls.env.ref('hr.contract_type_interim').id,
                'sex': 'male',
                'wage': 40.0,
            },
            {
                'name': 'Non-Employee 1',
                'date_version': '1122-01-01',
                'contract_date_start': '1122-01-01',
                'employee_type_id': cls.env.ref('hr.contract_type_intern').id,
                'sex': 'female',
                'department_id': cls.department_3.id,
                'wage': 30.0,
            },
        ])
        cls.employees[3].parent_id = cls.employees[0]
        cls.env['hr.employee.departure'].sudo().create([
            {
                'employee_id': cls.employees[3].id,
                'departure_date': '1125-06-06',
            },
            {
                'employee_id': cls.employees[4].id,
                'departure_date': '1111-07-07',  # Included in base year but not in reporting year
            },
        ])
        cls.env.user.partner_id.country_id = cls.env['res.country'].search([('code', '=', 'KR')])
        cls.env.cr.flush()  # Used to force departure records stored in DB
        cls.vsme_report = cls.env['esg.report'].create({
            'title': 'VSME Report',
            'report_type': 'vsme_basic',
            'start_date': '1125-01-01',
            'end_date': '1125-12-31',
            'base_year': 1110,
            'company_id': cls.env.company.id,
        })
        cls.csrd_report = cls.env['esg.report'].create({
            'title': 'CSRD Report',
            'report_type': 'csrd',
            'start_date': '1125-01-01',
            'end_date': '1125-12-31',
            'base_year': 1110,
            'company_id': cls.env.company.id,
        })

    def test_knowledge_report_hr_data_vsme(self):
        vsme_data = self.vsme_report._get_knowledge_report_hr_data()

        # Totals
        self.assertEqual(vsme_data.get('total_reporting'), '4')
        self.assertEqual(vsme_data.get('total_base'), '1')
        self.assertEqual(vsme_data.get('total_non_employee_reporting'), '2')
        self.assertEqual(vsme_data.get('total_non_employee_base'), '0')

        # Gender: Reporting Period
        self.assertEqual(vsme_data.get('female_reporting'), '2')
        self.assertEqual(vsme_data.get('female_pct_reporting'), '50.0')
        self.assertEqual(vsme_data.get('male_reporting'), '2')
        self.assertEqual(vsme_data.get('male_pct_reporting'), '50.0')
        self.assertEqual(vsme_data.get('other_reporting'), '0')
        self.assertEqual(vsme_data.get('other_pct_reporting'), '0.0')
        self.assertEqual(vsme_data.get('gender_not_reported_reporting'), '0')
        self.assertEqual(vsme_data.get('gender_not_reported_pct_reporting'), '0.0')

        # Gender: Base Period
        self.assertEqual(vsme_data.get('female_base'), '0')
        self.assertEqual(vsme_data.get('female_pct_base'), '0.0')
        self.assertEqual(vsme_data.get('male_base'), '1')
        self.assertEqual(vsme_data.get('male_pct_base'), '100.0')
        self.assertEqual(vsme_data.get('other_base'), '0')
        self.assertEqual(vsme_data.get('other_pct_base'), '0.0')
        self.assertEqual(vsme_data.get('gender_not_reported_base'), '0')
        self.assertEqual(vsme_data.get('gender_not_reported_pct_base'), '0.0')

        # Age Groups: Reporting Period
        self.assertEqual(vsme_data.get('age_lt30_reporting'), '1')
        self.assertEqual(vsme_data.get('age_lt30_pct_reporting'), '25.0')
        self.assertEqual(vsme_data.get('age_30_50_reporting'), '1')
        self.assertEqual(vsme_data.get('age_30_50_pct_reporting'), '25.0')
        self.assertEqual(vsme_data.get('age_gt50_reporting'), '1')
        self.assertEqual(vsme_data.get('age_gt50_pct_reporting'), '25.0')
        self.assertEqual(vsme_data.get('age_not_reported_reporting'), '1')
        self.assertEqual(vsme_data.get('age_not_reported_pct_reporting'), '25.0')

        # Age Groups: Base Period
        self.assertEqual(vsme_data.get('age_lt30_base'), '0')
        self.assertEqual(vsme_data.get('age_lt30_pct_base'), '0.0')
        self.assertEqual(vsme_data.get('age_30_50_base'), '0')
        self.assertEqual(vsme_data.get('age_30_50_pct_base'), '0.0')
        self.assertEqual(vsme_data.get('age_gt50_base'), '1')
        self.assertEqual(vsme_data.get('age_gt50_pct_base'), '100.0')
        self.assertEqual(vsme_data.get('age_not_reported_base'), '0')
        self.assertEqual(vsme_data.get('age_not_reported_pct_base'), '0.0')

        # Turnover & Employment
        self.assertEqual(vsme_data.get('left_reporting'), '1')
        self.assertEqual(vsme_data.get('avg_emp_reporting'), '3')
        self.assertEqual(vsme_data.get('turnover_reporting'), '33.33')
        self.assertEqual(vsme_data.get('left_base'), '0')
        self.assertEqual(vsme_data.get('avg_emp_base'), '1')
        self.assertEqual(vsme_data.get('turnover_base'), '0.0')

        # Contract Types: Reporting Period
        self.assertEqual(vsme_data.get('male_ft_reporting'), '2')
        self.assertEqual(vsme_data.get('male_pt_reporting'), '0')
        self.assertEqual(vsme_data.get('female_ft_reporting'), '2')
        self.assertEqual(vsme_data.get('female_pt_reporting'), '0')
        self.assertEqual(vsme_data.get('other_ft_reporting'), '0')
        self.assertEqual(vsme_data.get('other_pt_reporting'), '0')
        self.assertEqual(vsme_data.get('gender_not_reported_ft_reporting'), '0')
        self.assertEqual(vsme_data.get('gender_not_reported_pt_reporting'), '0')

        # Contract Types: Base Period
        self.assertEqual(vsme_data.get('male_ft_base'), '1')
        self.assertEqual(vsme_data.get('male_pt_base'), '0')
        self.assertEqual(vsme_data.get('female_ft_base'), '0')
        self.assertEqual(vsme_data.get('female_pt_base'), '0')
        self.assertEqual(vsme_data.get('other_ft_base'), '0')
        self.assertEqual(vsme_data.get('other_pt_base'), '0')
        self.assertEqual(vsme_data.get('gender_not_reported_ft_base'), '0')
        self.assertEqual(vsme_data.get('gender_not_reported_pt_base'), '0')

        # Pay Gap & Median Pay
        self.assertEqual(vsme_data.get('gender_pay_gap_reporting'), '-25.0')
        self.assertEqual(vsme_data.get('median_pay_male_reporting'), '0.46')
        self.assertEqual(vsme_data.get('median_pay_female_reporting'), '0.58')
        self.assertEqual(vsme_data.get('gender_pay_gap_base'), '0')
        self.assertEqual(vsme_data.get('median_pay_male_base'), '0.35')
        self.assertEqual(vsme_data.get('median_pay_female_base'), '0')

        # Miscellaneous
        self.assertEqual(vsme_data.get('non_salary_reporting'), '0')
        self.assertEqual(vsme_data.get('non_indep_reporting'), '1')
        self.assertEqual(vsme_data.get('non_temp_reporting'), '0')

    def test_knowledge_report_hr_data_vsme_2(self):
        # Data for HTML variables
        vsme_html_data = self.vsme_report._get_knowledge_report_hr_data(html_template_variables=True)

        self.assertEqual(vsme_html_data.get('total_reporting'), '4')
        self.assertEqual(vsme_html_data.get('total_base'), '1')
        self.assertEqual(vsme_html_data.get('total_non_employee_reporting'), '2')
        self.assertEqual(vsme_html_data.get('total_non_employee_base'), '0')

        # Country Employee Data (Reporting)
        country_report = vsme_html_data.get('country_employees_report_data', {})
        self.assertEqual(country_report.get('South Korea'), 1)

        # Country Employee Data (Base)
        self.assertEqual(vsme_html_data.get('country_employees_base_data'), {})

        # Management Gender Data (List of Dicts)
        management_data = vsme_html_data.get('report_gender_management_data', [])
        # Level 1 Assertions
        self.assertEqual(management_data[0].get('level'), 1)
        self.assertEqual(management_data[0].get('male'), 0)
        self.assertEqual(management_data[0].get('female'), 1)
        self.assertEqual(management_data[0].get('other'), 0)
        self.assertEqual(management_data[0].get('ratio'), 0.0)
        # Level 0 Assertions
        self.assertEqual(management_data[1].get('level'), 0)
        self.assertEqual(management_data[1].get('male'), 3)
        self.assertEqual(management_data[1].get('female'), 2)
        self.assertEqual(management_data[1].get('other'), 0)
        self.assertEqual(management_data[1].get('ratio'), 0.67)

    def test_knowledge_report_hr_data_csrd_1(self):
        data_csrd = self.csrd_report._get_knowledge_report_hr_data()

        # Totals and Headcount
        self.assertEqual(data_csrd.get('total_reporting'), '4')
        self.assertEqual(data_csrd.get('total_base'), '1')
        self.assertEqual(data_csrd.get('total_non_employee_reporting'), '2')
        self.assertEqual(data_csrd.get('total_non_employee_base'), '0')

        # Employment Type (Full-time/Part-time)
        self.assertEqual(data_csrd.get('ft_reporting'), '4')
        self.assertEqual(data_csrd.get('ft_pct_reporting'), '100.0')
        self.assertEqual(data_csrd.get('pt_reporting'), '0')
        self.assertEqual(data_csrd.get('pt_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('emp_type_not_reported_reporting'), '0')
        self.assertEqual(data_csrd.get('emp_type_not_reported_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('ft_base'), '1')
        self.assertEqual(data_csrd.get('ft_pct_base'), '100.0')
        self.assertEqual(data_csrd.get('pt_base'), '0')
        self.assertEqual(data_csrd.get('pt_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('emp_type_not_reported_base'), '0')
        self.assertEqual(data_csrd.get('emp_type_not_reported_pct_base'), '0.0')

        # Gender Metrics
        self.assertEqual(data_csrd.get('female_reporting'), '2')
        self.assertEqual(data_csrd.get('female_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('male_reporting'), '2')
        self.assertEqual(data_csrd.get('male_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('other_reporting'), '0')
        self.assertEqual(data_csrd.get('other_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('gender_not_reported_reporting'), '0')
        self.assertEqual(data_csrd.get('gender_not_reported_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('female_base'), '0')
        self.assertEqual(data_csrd.get('female_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('male_base'), '1')
        self.assertEqual(data_csrd.get('male_pct_base'), '100.0')
        self.assertEqual(data_csrd.get('other_base'), '0')
        self.assertEqual(data_csrd.get('other_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('gender_not_reported_base'), '0')
        self.assertEqual(data_csrd.get('gender_not_reported_pct_base'), '0.0')

        # Age Metrics
        self.assertEqual(data_csrd.get('age_lt30_reporting'), '1')
        self.assertEqual(data_csrd.get('age_lt30_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('age_30_50_reporting'), '1')
        self.assertEqual(data_csrd.get('age_30_50_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('age_gt50_reporting'), '1')
        self.assertEqual(data_csrd.get('age_gt50_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('age_not_reported_reporting'), '1')
        self.assertEqual(data_csrd.get('age_not_reported_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('age_lt30_base'), '0')
        self.assertEqual(data_csrd.get('age_lt30_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('age_30_50_base'), '0')
        self.assertEqual(data_csrd.get('age_30_50_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('age_gt50_base'), '1')
        self.assertEqual(data_csrd.get('age_gt50_pct_base'), '100.0')
        self.assertEqual(data_csrd.get('age_not_reported_base'), '0')
        self.assertEqual(data_csrd.get('age_not_reported_pct_base'), '0.0')

        # Contract Duration
        self.assertEqual(data_csrd.get('permanent_reporting'), '1')
        self.assertEqual(data_csrd.get('permanent_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('fixed_reporting'), '1')
        self.assertEqual(data_csrd.get('fixed_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('contract_not_reported_reporting'), '2')
        self.assertEqual(data_csrd.get('contract_not_reported_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('permanent_base'), '0')
        self.assertEqual(data_csrd.get('permanent_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('fixed_base'), '1')
        self.assertEqual(data_csrd.get('fixed_pct_base'), '100.0')
        self.assertEqual(data_csrd.get('contract_not_reported_base'), '0')
        self.assertEqual(data_csrd.get('contract_not_reported_pct_base'), '0.0')

        # Tenure (Years with Company)
        self.assertEqual(data_csrd.get('tenure_lt1_reporting'), '1')
        self.assertEqual(data_csrd.get('tenure_lt1_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('tenure_1_3_reporting'), '0')
        self.assertEqual(data_csrd.get('tenure_1_3_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('tenure_3_5_reporting'), '1')
        self.assertEqual(data_csrd.get('tenure_3_5_pct_reporting'), '25.0')
        self.assertEqual(data_csrd.get('tenure_gt5_reporting'), '0')
        self.assertEqual(data_csrd.get('tenure_gt5_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('tenure_not_reported_reporting'), '2')
        self.assertEqual(data_csrd.get('tenure_not_reported_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('tenure_lt1_base'), '0')
        self.assertEqual(data_csrd.get('tenure_lt1_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('tenure_1_3_base'), '0')
        self.assertEqual(data_csrd.get('tenure_1_3_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('tenure_3_5_base'), '0')
        self.assertEqual(data_csrd.get('tenure_3_5_pct_base'), '0.0')
        self.assertEqual(data_csrd.get('tenure_gt5_base'), '1')
        self.assertEqual(data_csrd.get('tenure_gt5_pct_base'), '100.0')
        self.assertEqual(data_csrd.get('tenure_not_reported_base'), '0')
        self.assertEqual(data_csrd.get('tenure_not_reported_pct_base'), '0.0')

        # Turnover and Retention
        self.assertEqual(data_csrd.get('left_reporting'), '1')
        self.assertEqual(data_csrd.get('avg_emp_reporting'), '3')
        self.assertEqual(data_csrd.get('turnover_reporting'), '33.33')
        self.assertEqual(data_csrd.get('left_base'), '0')
        self.assertEqual(data_csrd.get('avg_emp_base'), '1')
        self.assertEqual(data_csrd.get('turnover_base'), '0.0')

        # Non-Employee Gender Metrics
        self.assertEqual(data_csrd.get('non_employee_female_reporting'), '1')
        self.assertEqual(data_csrd.get('non_employee_female_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('non_employee_male_reporting'), '1')
        self.assertEqual(data_csrd.get('non_employee_male_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('non_employee_other_reporting'), '0')
        self.assertEqual(data_csrd.get('non_employee_other_pct_reporting'), '0.0')
        self.assertEqual(data_csrd.get('non_employee_gender_not_reported_reporting'), '0')
        self.assertEqual(data_csrd.get('non_employee_gender_not_reported_pct_reporting'), '0.0')

        # Work Force Diversity
        self.assertEqual(data_csrd.get('women_workforce_pct_reporting'), '50.0')
        self.assertEqual(data_csrd.get('employees_lt30_pct_reporting'), '16.67')
        self.assertEqual(data_csrd.get('employees_gt50_pct_reporting'), '16.67')
        self.assertEqual(data_csrd.get('women_management_pct_reporting'), '100.0')

    def test_knowledge_report_hr_data_csrd_2(self):
        # Data for HTML variables
        csrd_html_data = self.csrd_report._get_knowledge_report_hr_data(html_template_variables=True)

        # Basic Totals
        self.assertEqual(csrd_html_data.get('total_reporting'), '4')
        self.assertEqual(csrd_html_data.get('total_base'), '1')
        self.assertEqual(csrd_html_data.get('total_non_employee_reporting'), '2')
        self.assertEqual(csrd_html_data.get('total_non_employee_base'), '0')

        # Country Data
        self.assertEqual(csrd_html_data.get('country_employees_report_data'), {'South Korea': 1})
        self.assertEqual(csrd_html_data.get('country_employees_base_data'), {})

        # Department Employee Data
        dept_report = csrd_html_data.get('department_employees_report_data', {})
        self.assertEqual(dept_report.get(self.department_1), 1)
        self.assertEqual(dept_report.get(self.department_2), 1)
        dept_base = csrd_html_data.get('department_employees_base_data', {})
        self.assertEqual(dept_base.get(self.department_2), 1)

        # Non-Employee Type Data
        non_emp_type = csrd_html_data.get('report_non_employee_type_data', {})
        self.assertEqual(non_emp_type.get(self.env.ref('hr.contract_type_interim')), 1)
        self.assertEqual(non_emp_type.get(self.env.ref('hr.contract_type_intern')), 1)

        # Department Pay Gap Data
        pay_gap_dept = csrd_html_data.get('report_department_pay_gap_data', {})
        self.assertEqual(pay_gap_dept.get(self.department_1).get('female_median_hourly_salary'), 0.58)
        self.assertEqual(pay_gap_dept.get(self.department_1).get('pay_gap_percentage'), 0)
        self.assertEqual(pay_gap_dept.get(self.department_2).get('male_median_hourly_salary'), 0.46)

        # Contract Pay Gap Data
        contract_pay_gap = csrd_html_data.get('report_contract_pay_gap_data', {})
        self.assertEqual(contract_pay_gap.get(self.employee_type).get('pay_gap_percentage'), -25.0)
        self.assertEqual(contract_pay_gap.get(self.employee_type).get('male_median_hourly_salary'), 0.46)
        self.assertEqual(contract_pay_gap.get(self.employee_type).get('female_median_hourly_salary'), 0.58)

        # Country Pay Gap Data
        country_pay_gap = csrd_html_data.get('report_country_pay_gap_data', {})
        self.assertEqual(country_pay_gap.get(self.env.user.partner_id.country_id).get('male_median_hourly_salary'), 0.46)
        self.assertEqual(country_pay_gap.get(self.env.user.partner_id.country_id).get('pay_gap_percentage'), 0)

        # Empty Data
        self.assertEqual(csrd_html_data.get('report_non_employee_country_data'), {})
        self.assertEqual(csrd_html_data.get('base_non_employee_country_data'), {})
