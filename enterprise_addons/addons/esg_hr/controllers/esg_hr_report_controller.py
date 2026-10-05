from odoo.http import request
from odoo.addons.esg.controllers.esg_report_controller import EsgReportController


class EsgHrReportController(EsgReportController):

    def _get_template_variables(self, article):
        template_variables = super()._get_template_variables(article)
        if not (
            request.env.user.has_group('esg.esg_group_manager')
            and request.env.user.has_group('hr.group_hr_user')
            and (esg_report := article.inherited_esg_report_id)
        ):
            return template_variables

        data = esg_report._get_knowledge_report_hr_data()

        template_variables.update({
            # Data for Employees
            # Reporting Year
            '{{ total_reporting }}': data.get('total_reporting', ''),
            '{{ ft_reporting }}': data.get('ft_reporting', ''),
            '{{ ft_pct_reporting }}': data.get('ft_pct_reporting', ''),
            '{{ pt_reporting }}': data.get('pt_reporting', ''),
            '{{ pt_pct_reporting }}': data.get('pt_pct_reporting', ''),
            '{{ emp_type_not_reported_reporting }}': data.get('emp_type_not_reported_reporting', ''),
            '{{ emp_type_not_reported_pct_reporting }}': data.get('emp_type_not_reported_pct_reporting', ''),
            '{{ female_reporting }}': data.get('female_reporting', ''),
            '{{ female_pct_reporting }}': data.get('female_pct_reporting', ''),
            '{{ male_reporting }}': data.get('male_reporting', ''),
            '{{ male_pct_reporting }}': data.get('male_pct_reporting', ''),
            '{{ other_reporting }}': data.get('other_reporting', ''),
            '{{ other_pct_reporting }}': data.get('other_pct_reporting', ''),
            '{{ gender_not_reported_reporting }}': data.get('gender_not_reported_reporting', ''),
            '{{ gender_not_reported_pct_reporting }}': data.get('gender_not_reported_pct_reporting', ''),
            '{{ age_lt30_reporting }}': data.get('age_lt30_reporting', ''),
            '{{ age_lt30_pct_reporting }}': data.get('age_lt30_pct_reporting', ''),
            '{{ age_30_50_reporting }}': data.get('age_30_50_reporting', ''),
            '{{ age_30_50_pct_reporting }}': data.get('age_30_50_pct_reporting', ''),
            '{{ age_gt50_reporting }}': data.get('age_gt50_reporting', ''),
            '{{ age_gt50_pct_reporting }}': data.get('age_gt50_pct_reporting', ''),
            '{{ age_not_reported_reporting }}': data.get('age_not_reported_reporting', ''),
            '{{ age_not_reported_pct_reporting }}': data.get('age_not_reported_pct_reporting', ''),
            '{{ permanent_reporting }}': data.get('permanent_reporting', ''),
            '{{ permanent_pct_reporting }}': data.get('permanent_pct_reporting', ''),
            '{{ fixed_reporting }}': data.get('fixed_reporting', ''),
            '{{ fixed_pct_reporting }}': data.get('fixed_pct_reporting', ''),
            '{{ contract_not_reported_reporting }}': data.get('contract_not_reported_reporting', ''),
            '{{ contract_not_reported_pct_reporting }}': data.get('contract_not_reported_pct_reporting', ''),
            '{{ tenure_lt1_reporting }}': data.get('tenure_lt1_reporting', ''),
            '{{ tenure_lt1_pct_reporting }}': data.get('tenure_lt1_pct_reporting', ''),
            '{{ tenure_1_3_reporting }}': data.get('tenure_1_3_reporting', ''),
            '{{ tenure_1_3_pct_reporting }}': data.get('tenure_1_3_pct_reporting', ''),
            '{{ tenure_3_5_reporting }}': data.get('tenure_3_5_reporting', ''),
            '{{ tenure_3_5_pct_reporting }}': data.get('tenure_3_5_pct_reporting', ''),
            '{{ tenure_gt5_reporting }}': data.get('tenure_gt5_reporting', ''),
            '{{ tenure_gt5_pct_reporting }}': data.get('tenure_gt5_pct_reporting', ''),
            '{{ tenure_not_reported_reporting }}': data.get('tenure_not_reported_reporting', ''),
            '{{ tenure_not_reported_pct_reporting }}': data.get('tenure_not_reported_pct_reporting', ''),
            '{{ left_reporting }}': data.get('left_reporting', ''),
            '{{ avg_emp_reporting }}': data.get('avg_emp_reporting', ''),
            '{{ turnover_reporting }}': data.get('turnover_reporting', ''),
            '{{ male_ft_reporting }}': data.get('male_ft_reporting', ''),
            '{{ male_pt_reporting }}': data.get('male_pt_reporting', ''),
            '{{ female_ft_reporting }}': data.get('female_ft_reporting', ''),
            '{{ female_pt_reporting }}': data.get('female_pt_reporting', ''),
            '{{ other_ft_reporting }}': data.get('other_ft_reporting', ''),
            '{{ other_pt_reporting }}': data.get('other_pt_reporting', ''),
            '{{ gender_not_reported_ft_reporting }}': data.get('gender_not_reported_ft_reporting', ''),
            '{{ gender_not_reported_pt_reporting }}': data.get('gender_not_reported_pt_reporting', ''),
            '{{ gender_pay_gap_reporting }}': data.get('gender_pay_gap_reporting', ''),
            '{{ median_pay_male_reporting }}': data.get('median_pay_male_reporting', ''),
            '{{ median_pay_female_reporting }}': data.get('median_pay_female_reporting', ''),
             # Base Year
            '{{ total_base }}': data.get('total_base', ''),
            '{{ ft_base }}': data.get('ft_base', ''),
            '{{ ft_pct_base }}': data.get('ft_pct_base', ''),
            '{{ pt_base }}': data.get('pt_base', ''),
            '{{ pt_pct_base }}': data.get('pt_pct_base', ''),
            '{{ emp_type_not_reported_base }}': data.get('emp_type_not_reported_base', ''),
            '{{ emp_type_not_reported_pct_base }}': data.get('emp_type_not_reported_pct_base', ''),
            '{{ female_base }}': data.get('female_base', ''),
            '{{ female_pct_base }}': data.get('female_pct_base', ''),
            '{{ male_base }}': data.get('male_base', ''),
            '{{ male_pct_base }}': data.get('male_pct_base', ''),
            '{{ other_base }}': data.get('other_base', ''),
            '{{ other_pct_base }}': data.get('other_pct_base', ''),
            '{{ gender_not_reported_base }}': data.get('gender_not_reported_base', ''),
            '{{ gender_not_reported_pct_base }}': data.get('gender_not_reported_pct_base', ''),
            '{{ age_lt30_base }}': data.get('age_lt30_base', ''),
            '{{ age_lt30_pct_base }}': data.get('age_lt30_pct_base', ''),
            '{{ age_30_50_base }}': data.get('age_30_50_base', ''),
            '{{ age_30_50_pct_base }}': data.get('age_30_50_pct_base', ''),
            '{{ age_gt50_base }}': data.get('age_gt50_base', ''),
            '{{ age_gt50_pct_base }}': data.get('age_gt50_pct_base', ''),
            '{{ age_not_reported_base }}': data.get('age_not_reported_base', ''),
            '{{ age_not_reported_pct_base }}': data.get('age_not_reported_pct_base', ''),
            '{{ permanent_base }}': data.get('permanent_base', ''),
            '{{ permanent_pct_base }}': data.get('permanent_pct_base', ''),
            '{{ fixed_base }}': data.get('fixed_base', ''),
            '{{ fixed_pct_base }}': data.get('fixed_pct_base', ''),
            '{{ contract_not_reported_base }}': data.get('contract_not_reported_base', ''),
            '{{ contract_not_reported_pct_base }}': data.get('contract_not_reported_pct_base', ''),
            '{{ tenure_lt1_base }}': data.get('tenure_lt1_base', ''),
            '{{ tenure_lt1_pct_base }}': data.get('tenure_lt1_pct_base', ''),
            '{{ tenure_1_3_base }}': data.get('tenure_1_3_base', ''),
            '{{ tenure_1_3_pct_base }}': data.get('tenure_1_3_pct_base', ''),
            '{{ tenure_3_5_base }}': data.get('tenure_3_5_base', ''),
            '{{ tenure_3_5_pct_base }}': data.get('tenure_3_5_pct_base', ''),
            '{{ tenure_gt5_base }}': data.get('tenure_gt5_base', ''),
            '{{ tenure_gt5_pct_base }}': data.get('tenure_gt5_pct_base', ''),
            '{{ tenure_not_reported_base }}': data.get('tenure_not_reported_base', ''),
            '{{ tenure_not_reported_pct_base }}': data.get('tenure_not_reported_pct_base', ''),
            '{{ left_base }}': data.get('left_base', ''),
            '{{ avg_emp_base }}': data.get('avg_emp_base', ''),
            '{{ turnover_base }}': data.get('turnover_base', ''),
            '{{ male_ft_base }}': data.get('male_ft_base', ''),
            '{{ male_pt_base }}': data.get('male_pt_base', ''),
            '{{ female_ft_base }}': data.get('female_ft_base', ''),
            '{{ female_pt_base }}': data.get('female_pt_base', ''),
            '{{ other_ft_base }}': data.get('other_ft_base', ''),
            '{{ other_pt_base }}': data.get('other_pt_base', ''),
            '{{ gender_not_reported_ft_base }}': data.get('gender_not_reported_ft_base', ''),
            '{{ gender_not_reported_pt_base }}': data.get('gender_not_reported_pt_base', ''),
            '{{ gender_pay_gap_base }}': data.get('gender_pay_gap_base', ''),
            '{{ median_pay_male_base }}': data.get('median_pay_male_base', ''),
            '{{ median_pay_female_base }}': data.get('median_pay_female_base', ''),
            # Data for Non-Employees
            # Reporting Year
            '{{ total_non_employee_reporting }}': data.get('total_non_employee_reporting', ''),
            '{{ total_non_employee_base }}': data.get('total_non_employee_base', ''),
            '{{ non_employee_female_reporting }}': data.get('non_employee_female_reporting', ''),
            '{{ non_employee_female_pct_reporting }}': data.get('non_employee_female_pct_reporting', ''),
            '{{ non_employee_male_reporting }}': data.get('non_employee_male_reporting', ''),
            '{{ non_employee_male_pct_reporting }}': data.get('non_employee_male_pct_reporting', ''),
            '{{ non_employee_other_reporting }}': data.get('non_employee_other_reporting', ''),
            '{{ non_employee_other_pct_reporting }}': data.get('non_employee_other_pct_reporting', ''),
            '{{ non_employee_gender_not_reported_reporting }}': data.get('non_employee_gender_not_reported_reporting', ''),
            '{{ non_employee_gender_not_reported_pct_reporting }}': data.get('non_employee_gender_not_reported_pct_reporting', ''),
            '{{ non_salary_reporting }}': data.get('non_salary_reporting', ''),
            '{{ non_indep_reporting }}': data.get('non_indep_reporting', ''),
            '{{ non_temp_reporting }}': data.get('non_temp_reporting', ''),
            # Base Year
            '{{ non_employee_female_base }}': data.get('non_employee_female_base', ''),
            '{{ non_employee_female_pct_base }}': data.get('non_employee_female_pct_base', ''),
            '{{ non_employee_male_base }}': data.get('non_employee_male_base', ''),
            '{{ non_employee_male_pct_base }}': data.get('non_employee_male_pct_base', ''),
            '{{ non_employee_other_base }}': data.get('non_employee_other_base', ''),
            '{{ non_employee_other_pct_base }}': data.get('non_employee_other_pct_base', ''),
            '{{ non_employee_gender_not_reported_base }}': data.get('non_employee_gender_not_reported_base', ''),
            '{{ non_employee_gender_not_reported_pct_base }}': data.get('non_employee_gender_not_reported_pct_base', ''),
            '{{ non_salary_base }}': data.get('non_salary_base', ''),
            '{{ non_indep_base }}': data.get('non_indep_base', ''),
            '{{ non_temp_base }}': data.get('non_temp_base', ''),
            # Data for Employees + Non-Employees
            '{{ women_workforce_pct_reporting }}': data.get('women_workforce_pct_reporting', ''),
            '{{ women_management_pct_reporting }}': data.get('women_management_pct_reporting', ''),
            '{{ employees_lt30_pct_reporting }}': data.get('employees_lt30_pct_reporting', ''),
            '{{ employees_gt50_pct_reporting }}': data.get('employees_gt50_pct_reporting', ''),
        })

        return template_variables

    def _get_html_template_variables(self, article):
        html_template_variables = super()._get_html_template_variables(article)
        if not (
            request.env.user.has_group('esg.esg_group_manager')
            and request.env.user.has_group('hr.group_hr_user')
            and (esg_report := article.inherited_esg_report_id)
        ):
            return html_template_variables

        data = esg_report._get_knowledge_report_hr_data(html_template_variables=True)

        # Reporting Year
        report_total_employees_count = int(data.get('total_reporting', 0))
        html_template_variables.update({
            '{{ country_employees_table }}': '',
            '{{ department_employees_table }}': '',
        })
        # Base Year
        has_base_year = esg_report._has_valid_base_year()
        base_total_employees_count = int(data.get('total_base', 0))

        # Data for Table: Geography/Region
        # Reporting Year
        if country_employees_report_data := data.get('country_employees_report_data'):
            # Base Year
            country_employees_base_data = data.get('country_employees_base_data', {})
            rows = []
            for report_country_name, report_country_count in country_employees_report_data.items():
                base_country_count = country_employees_base_data.get(report_country_name, 0) if base_total_employees_count else ''
                base_country_percentage = round((base_country_count / base_total_employees_count) * 100, 2) if base_total_employees_count else ''
                rows.append({
                    'name': report_country_name,
                    'r_count': report_country_count,
                    'r_pct': round((report_country_count / report_total_employees_count) * 100, 2),
                    'b_count': base_country_count,
                    'b_pct': base_country_percentage,
                })
            for base_country_name, base_country_count in country_employees_base_data.items():
                if base_country_name in country_employees_report_data:
                    continue
                rows.append({
                    'name': base_country_name,
                    'r_count': 0,
                    'r_pct': 0.0,
                    'b_count': base_country_count,
                    'b_pct': round((base_country_count / base_total_employees_count) * 100, 2) if base_total_employees_count else '',
                })
            rows.extend([
                {
                    'name': 'Not Reported',
                    'r_count': report_total_employees_count - sum(country_employees_report_data.values()),
                    'r_pct': round(((report_total_employees_count - sum(country_employees_report_data.values())) / report_total_employees_count) * 100, 2) if report_total_employees_count else 0,
                    'b_count': base_total_employees_count - sum(country_employees_base_data.values()) if base_total_employees_count else '',
                    'b_pct': round(((base_total_employees_count - sum(country_employees_base_data.values())) / base_total_employees_count) * 100, 2) if base_total_employees_count else '',
                },
                {
                    'name': 'Total Employees',
                    'r_count': report_total_employees_count,
                    'r_pct': '100',
                    'b_count': base_total_employees_count or '',
                    'b_pct': '100' if base_total_employees_count else '',
                },
            ])
            employees_number_per_country_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_country_employees_table', {
                'rows': rows,
                'has_base_year': has_base_year,
            })
            html_template_variables['{{ country_employees_table }}'] = employees_number_per_country_table

        # Data for Table: Job Category/Function
        # Reporting Year
        if department_employees_report_data := data.get('department_employees_report_data'):
            # Base Year
            department_employees_base_data = data.get('department_employees_base_data', {})
            rows = []
            for report_department, report_count in department_employees_report_data.items():
                base_count = department_employees_base_data.get(report_department, 0) if base_total_employees_count else ''
                base_percentage = round((base_count / base_total_employees_count) * 100, 2) if base_total_employees_count else ''
                rows.append({
                    'name': report_department.name,
                    'r_count': report_count,
                    'r_pct': round((report_count / report_total_employees_count) * 100, 2),
                    'b_count': base_count,
                    'b_pct': base_percentage,
                })
            for base_department, base_count in department_employees_base_data.items():
                if base_department in department_employees_report_data:
                    continue
                rows.append({
                    'name': base_department.name,
                    'r_count': 0,
                    'r_pct': 0.0,
                    'b_count': base_count,
                    'b_pct': round((base_count / base_total_employees_count) * 100, 2) if base_total_employees_count else '',
                })
            rows.extend([
                {
                    'name': 'Not Reported',
                    'r_count': report_total_employees_count - sum(department_employees_report_data.values()),
                    'r_pct': round(((report_total_employees_count - sum(department_employees_report_data.values())) / report_total_employees_count) * 100, 2) if report_total_employees_count else 0,
                    'b_count': base_total_employees_count - sum(department_employees_base_data.values()) if base_total_employees_count else '',
                    'b_pct': round(((base_total_employees_count - sum(department_employees_base_data.values())) / base_total_employees_count) * 100, 2) if base_total_employees_count else '',
                },
                {
                    'name': 'Total Employees',
                    'r_count': report_total_employees_count,
                    'r_pct': '100',
                    'b_count': base_total_employees_count or '',
                    'b_pct': '100' if base_total_employees_count else '',
                },
            ])
            employees_number_per_department_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_department_employees_table', {
                'rows': rows,
                'has_base_year': has_base_year,
            })
            html_template_variables['{{ department_employees_table }}'] = employees_number_per_department_table

        # Data for Non-Employees
        html_template_variables.update({
            '{{ non_employees_types_table }}': '',
            '{{ country_non_employees_table }}': '',
            '{{ department_non_employees_table }}': '',
        })
        report_total_non_employees_count = int(data.get('total_non_employee_reporting', 0))
        base_total_non_employees_count = int(data.get('total_non_employee_base', 0))

        # Data for Table: Employment Type (Non-Employees)
        if report_non_employee_type_data := data.get('report_non_employee_type_data'):
            # Base Year
            base_non_employee_type_data = data.get('base_non_employee_type_data', {})
            rows = []
            for employee_type, count in report_non_employee_type_data.items():
                base_count = base_non_employee_type_data.get(employee_type, 0) if base_total_non_employees_count else ''
                rows.append({
                    'name': employee_type.name,
                    'r_count': count,
                    'r_pct': round((count / report_total_non_employees_count) * 100, 2),
                    'b_count': base_count,
                    'b_pct': round((base_count / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else '',
                })
            for employee_type, count in base_non_employee_type_data.items():
                if employee_type in report_non_employee_type_data:
                    continue
                rows.append({
                    'name': employee_type.name,
                    'r_count': 0,
                    'r_pct': 0.0,
                    'b_count': count,
                    'b_pct': round((count / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else '',
                })
            rows.append({
                'name': 'Total Non-Employees',
                'r_count': report_total_non_employees_count,
                'r_pct': '100',
                'b_count': base_total_non_employees_count or '',
                'b_pct': '100' if base_total_non_employees_count else '',
            })
            non_employees_types_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_type_non_employees_table', {
                'rows': rows,
                'has_base_year': has_base_year,
            })
            html_template_variables['{{ non_employees_types_table }}'] = non_employees_types_table

        # Data for Table: Geography/Region (Non-Employees)
        # Reporting Year
        if report_non_employee_country_data := data.get('report_non_employee_country_data'):
            # Base Year
            base_non_employee_country_data = data.get('base_non_employee_country_data', {})
            rows = []
            for report_country_name, report_country_count in report_non_employee_country_data.items():
                base_country_count = base_non_employee_country_data.get(report_country_name, 0) if base_total_non_employees_count else ''
                base_country_percentage = round((base_country_count / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else ''
                rows.append({
                    'name': report_country_name,
                    'r_count': report_country_count,
                    'r_pct': round((report_country_count / report_total_non_employees_count) * 100, 2),
                    'b_count': base_country_count,
                    'b_pct': base_country_percentage,
                })
            for base_country_name, base_country_count in base_non_employee_country_data.items():
                if base_country_name in report_non_employee_country_data:
                    continue
                rows.append({
                    'name': base_country_name,
                    'r_count': 0,
                    'r_pct': 0.0,
                    'b_count': base_country_count,
                    'b_pct': round((base_country_count / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count > 0 else '',
                })
            rows.extend([
                {
                    'name': 'Not Reported',
                    'r_count': report_total_non_employees_count - sum(report_non_employee_country_data.values()),
                    'r_pct': round(((report_total_non_employees_count - sum(report_non_employee_country_data.values())) / report_total_non_employees_count) * 100, 2) if report_total_non_employees_count else 0,
                    'b_count': base_total_non_employees_count - sum(base_non_employee_country_data.values()) if base_total_non_employees_count else '',
                    'b_pct': round(((base_total_non_employees_count - sum(base_non_employee_country_data.values())) / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else '',
                },
                {
                    'name': 'Total Non-Employees',
                    'r_count': report_total_non_employees_count,
                    'r_pct': '100',
                    'b_count': base_total_non_employees_count or '',
                    'b_pct': '100' if base_total_non_employees_count else '',
                },
            ])
            country_non_employees_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_department_non_employees_table', {
                'rows': rows,
                'has_base_year': has_base_year,
            })
            html_template_variables['{{ country_non_employees_table }}'] = country_non_employees_table

        # Data for Table: Job Category/Function (Non-Employees)
        # Reporting Year
        if report_non_employee_department_data := data.get('report_non_employee_department_data'):
            # Base Year
            base_non_employee_department_data = data.get('base_non_employee_department_data', {})
            rows = []
            for report_department, report_count in report_non_employee_department_data.items():
                base_count = base_non_employee_department_data.get(report_department, 0) if base_total_non_employees_count else ''
                base_percentage = round((base_count / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else ''
                rows.append({
                    'name': report_department.name,
                    'r_count': report_count,
                    'r_pct': round((report_count / report_total_non_employees_count) * 100, 2),
                    'b_count': base_count,
                    'b_pct': base_percentage,
                })
            for base_department, base_count in base_non_employee_department_data.items():
                if base_department in report_non_employee_department_data:
                    continue
                rows.append({
                    'name': base_department.name,
                    'r_count': 0,
                    'r_pct': 0.0,
                    'b_count': base_count,
                    'b_pct': round((base_count / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else '',
                })
            rows.extend([
                {
                    'name': 'Not Reported',
                    'r_count': report_total_non_employees_count - sum(report_non_employee_department_data.values()),
                    'r_pct': round(((report_total_non_employees_count - sum(report_non_employee_department_data.values())) / report_total_non_employees_count) * 100, 2) if report_total_non_employees_count else 0,
                    'b_count': base_total_non_employees_count - sum(base_non_employee_department_data.values()) if base_total_non_employees_count else '',
                    'b_pct': round(((base_total_non_employees_count - sum(base_non_employee_department_data.values())) / base_total_non_employees_count) * 100, 2) if base_total_non_employees_count else '',
                },
                {
                    'name': 'Total Non-Employees',
                    'r_count': report_total_non_employees_count,
                    'r_pct': '100',
                    'b_count': base_total_non_employees_count or '',
                    'b_pct': '100' if base_total_non_employees_count else '',
                },
            ])
            department_non_employees_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_department_non_employees_table', {
                'rows': rows,
                'has_base_year': has_base_year,
            })
            html_template_variables['{{ department_non_employees_table }}'] = department_non_employees_table

        # Data for Employees + Non-Employees
        html_template_variables.update({
            '{{ department_all_employees_pay_gap_table }}': '',
            '{{ contract_type_all_employees_pay_gap_table }}': '',
            '{{ country_all_employees_pay_gap_table }}': '',
            '{{ management_level_gender_table }}': '',
        })

        # Data for Tables: Remuneration Metrics
        # Data for Table: Job Category/Function Pay Gap (Employees + Non-Employees)
        # Reporting Year
        if report_department_pay_gap_data := data.get('report_department_pay_gap_data'):
            rows = []
            for report_department, pay_gap_data in report_department_pay_gap_data.items():
                rows.append({
                    'name': report_department.name,
                    'male_median_hourly_salary': round(pay_gap_data['male_median_hourly_salary'], 2),
                    'female_median_hourly_salary': round(pay_gap_data['female_median_hourly_salary'], 2),
                    'pay_gap_percentage': round(pay_gap_data['pay_gap_percentage'], 2),
                })
            department_all_employees_pay_gap_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_department_pay_gap_table', {
                'rows': rows,
            })
            html_template_variables['{{ department_all_employees_pay_gap_table }}'] = department_all_employees_pay_gap_table

        # Data for Table: Contract Type Pay Gap (Employees + Non-Employees)
        # Reporting Year
        if report_contract_pay_gap_data := data.get('report_contract_pay_gap_data'):
            rows = []
            for contract_type, pay_gap_data in report_contract_pay_gap_data.items():
                rows.append({
                    'name': contract_type.name,
                    'male_median_hourly_salary': round(pay_gap_data['male_median_hourly_salary'], 2),
                    'female_median_hourly_salary': round(pay_gap_data['female_median_hourly_salary'], 2),
                    'pay_gap_percentage': round(pay_gap_data['pay_gap_percentage'], 2),
                })
            contract_type_all_employees_pay_gap_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_contract_type_pay_gap_table', {
                'rows': rows,
            })
            html_template_variables['{{ contract_type_all_employees_pay_gap_table }}'] = contract_type_all_employees_pay_gap_table

        # Data for Table: Country Pay Gap (Employees + Non-Employees)
        # Reporting Year
        if report_country_pay_gap_data := data.get('report_country_pay_gap_data'):
            rows = []
            for country, pay_gap_data in report_country_pay_gap_data.items():
                rows.append({
                    'name': country.name,
                    'male_median_hourly_salary': round(pay_gap_data['male_median_hourly_salary'], 2),
                    'female_median_hourly_salary': round(pay_gap_data['female_median_hourly_salary'], 2),
                    'pay_gap_percentage': round(pay_gap_data['pay_gap_percentage'], 2),
                })
            country_all_employees_pay_gap_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_country_pay_gap_table', {
                'rows': rows,
            })
            html_template_variables['{{ country_all_employees_pay_gap_table }}'] = country_all_employees_pay_gap_table

        # Gender Ratio at Management Level (Employees + Non-Employees)
        # Reporting Year
        if report_gender_management_data := data.get('report_gender_management_data'):
            rows = []
            for data in report_gender_management_data:
                rows.append({
                    'level': data['level'],
                    'female': data['female'],
                    'male': data['male'],
                    'other': data['other'],
                    'ratio': data['ratio'],
                })
            management_level_gender_table = request.env['ir.qweb']._render('esg_hr.esg_csrd_hr_report_management_level_gender_table', {
                'rows': rows,
            })
            html_template_variables['{{ management_level_gender_table }}'] = management_level_gender_table

        return html_template_variables
