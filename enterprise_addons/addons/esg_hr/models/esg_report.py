import statistics

from datetime import date
from dateutil.relativedelta import relativedelta

from odoo import models
from odoo.fields import Domain
from odoo.tools import SQL


class EsgReport(models.Model):
    _inherit = 'esg.report'

    def _get_knowledge_report_hr_data(self, html_template_variables=False):
        def get_valid_employee_version_ids(start_date, end_date, is_employee_type=None):
            employee_type_condition = SQL("")
            if is_employee_type:
                employee_type_condition = SQL(" AND hv.employee_type_id = %(employee_type_id)s ", employee_type_id=self.env.ref('hr.contract_type_employee').id)
            elif is_employee_type is False:
                employee_type_condition = SQL(" AND hv.employee_type_id != %(employee_type_id)s ", employee_type_id=self.env.ref('hr.contract_type_employee').id)

            self.env.cr.execute(SQL(
                """
                SELECT DISTINCT hv.id
                FROM hr_version hv
                JOIN (
                    SELECT employee_id, MAX(date_version) AS max_date
                    FROM hr_version
                    WHERE date_version <= %(end_date)s
                GROUP BY employee_id
                ) latest_employee_version
                    ON hv.employee_id = latest_employee_version.employee_id
                AND hv.date_version = latest_employee_version.max_date
            LEFT JOIN hr_employee_departure hed ON hv.departure_id = hed.id
                WHERE hv.active = TRUE
                AND (hed.departure_date IS NULL OR hed.departure_date >= %(start_date)s)
                %(employee_type_condition)s
                """,
                start_date=start_date,
                end_date=end_date,
                employee_type_condition=employee_type_condition,
            ))

            return tuple(row[0] for row in self.env.cr.fetchall())

        def get_employment_type_data(version_ids, total_employees_count):
            data = {
                'employees_full_time_count': 0,
                'employees_full_time_percentage': 0,
                'employees_part_time_count': 0,
                'employees_part_time_percentage': 0,
            }
            if not version_ids:
                return data
            self.env.cr.execute(SQL(
                """
                SELECT COUNT(hv.id)
                FROM hr_version hv, resource_calendar rc
                WHERE hv.id IN %(ids)s
                AND hv.resource_calendar_id = rc.id
                AND rc.hours_per_week = rc.full_time_required_hours
                """,
                ids=version_ids,
            ))
            result = self.env.cr.fetchall()[0][0]
            employees_emp_type_not_reported_count = self.env['hr.version'].sudo().search_count(
                domain=[('id', 'in', version_ids), ('resource_calendar_id', '=', False)],
            )
            employees_part_time_count = total_employees_count - result - employees_emp_type_not_reported_count
            data.update({
                'employees_full_time_count': result,
                'employees_full_time_percentage': round((result / total_employees_count) * 100, 2),
                'employees_part_time_count': employees_part_time_count,
                'employees_part_time_percentage': round((employees_part_time_count / total_employees_count) * 100, 2),
                'employees_emp_type_not_reported_count': employees_emp_type_not_reported_count,
                'employees_emp_type_not_reported_percentage': round((employees_emp_type_not_reported_count / total_employees_count) * 100, 2),
            })
            return data

        def get_gender_data(version_ids, total_employees_count):
            employees_count_per_sex = dict(
                self.env['hr.version'].sudo()._read_group(
                    domain=[('id', 'in', version_ids)],
                    groupby=['sex'],
                    aggregates=['id:count'],
                )
            )
            employees_female_count = employees_count_per_sex.get('female', 0)
            employees_female_percentage = round((employees_female_count / total_employees_count) * 100, 2)
            employees_male_count = employees_count_per_sex.get('male', 0)
            employees_male_percentage = round((employees_male_count / total_employees_count) * 100, 2)
            employees_other_count = employees_count_per_sex.get('other', 0)
            employees_other_percentage = round((employees_other_count / total_employees_count) * 100, 2)
            employees_unknown_count = total_employees_count - employees_female_count - employees_male_count - employees_other_count
            employees_unknown_percentage = round((employees_unknown_count / total_employees_count) * 100, 2)
            return {
                'employees_female_count': employees_female_count,
                'employees_female_percentage': employees_female_percentage,
                'employees_male_count': employees_male_count,
                'employees_male_percentage': employees_male_percentage,
                'employees_other_count': employees_other_count,
                'employees_other_percentage': employees_other_percentage,
                'employees_unknown_count': employees_unknown_count,
                'employees_unknown_percentage': employees_unknown_percentage,
            }

        def get_age_group_data(version_ids, total_employees_count, end_date):
            HrEmployee = self.env['hr.employee']
            date_30_years_ago = end_date - relativedelta(years=30)
            date_50_years_ago = end_date - relativedelta(years=50)
            employees_age_below_30_count = HrEmployee.sudo().search_count(
                domain=Domain([('version_ids', 'in', version_ids), ('birthday', '>', date_30_years_ago)]),
            )
            employees_age_below_30_percentage = round((employees_age_below_30_count / total_employees_count) * 100, 2)
            employees_age_between_30_and_50_count = HrEmployee.sudo().search_count(
                domain=Domain([('version_ids', 'in', version_ids), ('birthday', '<=', date_30_years_ago), ('birthday', '>=', date_50_years_ago)]),
            )
            employees_age_between_30_and_50_percentage = round((employees_age_between_30_and_50_count / total_employees_count) * 100, 2)
            employees_age_above_50_count = HrEmployee.sudo().search_count(
                domain=Domain([('version_ids', 'in', version_ids), ('birthday', '<', date_50_years_ago)]),
            )
            employees_age_above_50_percentage = round((employees_age_above_50_count / total_employees_count) * 100, 2)
            employees_age_unknown_count = total_employees_count - employees_age_below_30_count - employees_age_between_30_and_50_count - employees_age_above_50_count
            employees_age_unknown_percentage = round((employees_age_unknown_count / total_employees_count) * 100, 2)
            return {
                'employees_age_below_30_count': employees_age_below_30_count,
                'employees_age_below_30_percentage': employees_age_below_30_percentage,
                'employees_age_between_30_and_50_count': employees_age_between_30_and_50_count,
                'employees_age_between_30_and_50_percentage': employees_age_between_30_and_50_percentage,
                'employees_age_above_50_count': employees_age_above_50_count,
                'employees_age_above_50_percentage': employees_age_above_50_percentage,
                'employees_age_unknown_count': employees_age_unknown_count,
                'employees_age_unknown_percentage': employees_age_unknown_percentage,
            }

        def get_contract_type_data(version_ids, total_employees_count, start_date, end_date):
            HrVersion = self.env['hr.version']
            employees_permanent_contract_count = HrVersion.sudo().search_count(
                domain=[('id', 'in', version_ids), ('contract_date_start', '<=', end_date), ('contract_date_end', '=', False)]
            )
            employees_permanent_contract_percentage = round((employees_permanent_contract_count / total_employees_count) * 100, 2)
            employees_fixed_term_contract_count = HrVersion.sudo().search_count(
                domain=[('id', 'in', version_ids), ('contract_date_start', '<=', end_date), ('contract_date_end', '>=', start_date)]
            )
            employees_fixed_term_contract_percentage = round((employees_fixed_term_contract_count / total_employees_count) * 100, 2)
            employees_unkown_contract_count = total_employees_count - employees_permanent_contract_count - employees_fixed_term_contract_count
            employees_unkown_contract_percentage = round((employees_unkown_contract_count / total_employees_count) * 100, 2)
            return {
                'employees_permanent_contract_count': employees_permanent_contract_count,
                'employees_permanent_contract_percentage': employees_permanent_contract_percentage,
                'employees_fixed_term_contract_count': employees_fixed_term_contract_count,
                'employees_fixed_term_contract_percentage': employees_fixed_term_contract_percentage,
                'employees_unkown_contract_count': employees_unkown_contract_count,
                'employees_unkown_contract_percentage': employees_unkown_contract_percentage,
            }

        def get_country_employees_data(version_ids):
            if not version_ids:
                return {}
            self.env.cr.execute(SQL(
                """
                SELECT rc.name, COUNT(he.id)
                FROM hr_version hv, hr_employee he, res_partner rp, res_country rc
                WHERE hv.id IN %(ids)s
                AND hv.employee_id = he.id
                AND he.work_contact_id = rp.id
                AND rp.country_id = rc.id
            GROUP BY rc.name
            ORDER BY COUNT(he.id) DESC
                """,
                ids=version_ids,
            ))
            result = self.env.cr.dictfetchall()
            return {
                next(iter(item['name'].values()), ''): item['count']
                for item in result
            }

        def get_department_employees_data(version_ids):
            return dict(
                self.env['hr.version'].sudo()._read_group(
                    domain=[('id', 'in', version_ids), ('department_id', '!=', False)],
                    groupby=['department_id'],
                    aggregates=['__count'],
                    order='__count desc',
                )
            )

        def get_employee_turnover_data(start_date, end_date):
            leaving_employees_count = self.env['hr.employee'].sudo().with_context(active_test=False).search_count(
                domain=[
                    ('version_ids', 'any', [
                        ('departure_date', '>=', start_date),
                        ('departure_date', '<=', end_date),
                    ]),
                ],
            )
            employees_start_year_count = len(get_valid_employee_version_ids(start_date, start_date, is_employee_type=True))
            employees_end_year_count = len(get_valid_employee_version_ids(end_date, end_date, is_employee_type=True))
            employees_avg_count = (employees_start_year_count + employees_end_year_count) // 2
            employees_turnover_rate = round((leaving_employees_count / employees_avg_count) * 100, 2) if employees_avg_count > 0 else 0
            return {
                'leaving_employees_count': leaving_employees_count,
                'employees_avg_count': employees_avg_count,
                'employees_turnover_rate': employees_turnover_rate,
            }

        def get_employee_type_data(version_ids):
            return dict(
                self.env['hr.version'].sudo()._read_group(
                    domain=[('id', 'in', version_ids)],
                    groupby=['employee_type_id'],
                    aggregates=['id:count'],
                )
            )

        def get_employee_tenure_data(start_date, end_date, total_employees_count):
            self.env.cr.execute(SQL(
                """
            WITH unique_records AS (
                    -- Step 1: Filter by type and handle duplicates
                SELECT DISTINCT
                        hv.employee_id,
                        hv.contract_date_start,
                        COALESCE(hv.contract_date_end, %(end_date)s) AS contract_date_end
                    FROM hr_version hv
            LEFT JOIN hr_employee_departure hed ON hv.departure_id = hed.id
                WHERE hv.contract_date_start IS NOT NULL
                    AND hv.employee_type_id = %(employee_type_id)s
                    AND hv.date_version <= %(end_date)s
                    AND (hed.departure_date IS NULL OR hed.departure_date >= %(start_date)s)
                    AND hv.active = TRUE
                ),
                employee_tenure AS (
                    -- Step 2: Sum duration per employee
                SELECT employee_id,
                        SUM(contract_date_end - contract_date_start) AS total_days
                    FROM unique_records
                GROUP BY employee_id
                ),
                tenure_buckets AS (
                    -- Step 3: Categorize into tenure ranges
                    -- 1 year = 365 days | 3 years = 1095 days | 5 years = 1825 days
                SELECT employee_id,
                        CASE
                            WHEN total_days < 365 THEN 'tenure_lt1'
                            WHEN total_days >= 365 AND total_days < 1095 THEN 'tenure_1_3'
                            WHEN total_days >= 1095 AND total_days <= 1825 THEN 'tenure_3_5'
                            ELSE 'tenure_gt5'
                        END AS tenure_range
                    FROM employee_tenure
                )
                    -- Step 4: Aggregate counts
                SELECT tenure_range,
                        COUNT(*) AS employee_count
                    FROM tenure_buckets
                GROUP BY tenure_range
                """,
                start_date=start_date,
                end_date=end_date,
                employee_type_id=self.env.ref('hr.contract_type_employee').id,
            ))

            data = {}
            if result := self.env.cr.dictfetchall():
                data = {
                    item['tenure_range']: item['employee_count']
                    for item in result
                }
            tenure_lt1 = data.get('tenure_lt1', 0)
            tenure_1_3 = data.get('tenure_1_3', 0)
            tenure_3_5 = data.get('tenure_3_5', 0)
            tenure_gt5 = data.get('tenure_gt5', 0)
            tenure_not_reported = total_employees_count - tenure_lt1 - tenure_1_3 - tenure_3_5 - tenure_gt5
            tenure_lt1_pct = round((tenure_lt1 / total_employees_count) * 100, 2)
            tenure_1_3_pct = round((tenure_1_3 / total_employees_count) * 100, 2)
            tenure_3_5_pct = round((tenure_3_5 / total_employees_count) * 100, 2)
            tenure_gt5_pct = round((tenure_gt5 / total_employees_count) * 100, 2)
            tenure_not_reported_pct = round((tenure_not_reported / total_employees_count) * 100, 2)

            return {
                'tenure_lt1': tenure_lt1,
                'tenure_lt1_pct': tenure_lt1_pct,
                'tenure_1_3': tenure_1_3,
                'tenure_1_3_pct': tenure_1_3_pct,
                'tenure_3_5': tenure_3_5,
                'tenure_3_5_pct': tenure_3_5_pct,
                'tenure_gt5': tenure_gt5,
                'tenure_gt5_pct': tenure_gt5_pct,
                'tenure_not_reported': tenure_not_reported,
                'tenure_not_reported_pct': tenure_not_reported_pct,
            }

        def get_pay_gap_data(version_ids):
            versions_by_sex = dict(self.env['hr.version'].sudo()._read_group(
                domain=[('id', 'in', version_ids)],
                groupby=['sex'],
                aggregates=['id:recordset'],
            ))
            male_versions = versions_by_sex.get('male', self.env['hr.version'])
            female_versions = versions_by_sex.get('female', self.env['hr.version'])

            # Normalize wages to a hourly wage
            def get_wages(versions):
                wages = []
                for version in versions:
                    if wage := version.sudo()._get_normalized_wage():
                        wages.append(wage)
                return wages

            male_wages = get_wages(male_versions)
            female_wages = get_wages(female_versions)

            male_median = statistics.median(male_wages) if male_wages else 0
            female_median = statistics.median(female_wages) if female_wages else 0
            pay_gap = round((male_median - female_median) / male_median * 100, 2) if male_median and female_median else 0

            return {
                'male_median_hourly_salary': round(male_median, 2),
                'female_median_hourly_salary': round(female_median, 2),
                'pay_gap_percentage': pay_gap,
            }

        def get_department_pay_gap_data(version_ids):
            data = {}
            for department, version_ids in self.env['hr.version'].sudo()._read_group(
                domain=[('id', 'in', version_ids), ('department_id', '!=', False)],
                groupby=['department_id'],
                aggregates=['id:array_agg'],
            ):
                data[department] = get_pay_gap_data(version_ids)
            return data

        def get_contract_type_pay_gap_data(version_ids):
            data = {}
            for contract_type, version_ids in self.env['hr.version'].sudo()._read_group(
                domain=[('id', 'in', version_ids), ('employee_type_id', '!=', False)],
                groupby=['employee_type_id'],
                aggregates=['id:array_agg'],
            ):
                data[contract_type] = get_pay_gap_data(version_ids)
            return data

        def get_country_pay_gap_data(version_ids):
            data = {}
            for country, version_ids in self.env['hr.version'].sudo()._read_group(
                domain=[('id', 'in', version_ids), ('employee_id.work_contact_id.country_id', '!=', False)],
                groupby=['employee_id.work_contact_id.country_id'],
                aggregates=['id:array_agg'],
            ):
                data[country] = get_pay_gap_data(version_ids)
            return data

        def get_employment_type_per_gender_data(version_ids, total_employees_count):
            data = {
                'male_ft_count': 0,
                'male_pt_count': 0,
                'female_ft_count': 0,
                'female_pt_count': 0,
                'other_ft_count': 0,
                'other_pt_count': 0,
                'gender_not_reported_ft_count': 0,
                'gender_not_reported_pt_count': 0,
            }
            if not version_ids:
                return data
            self.env.cr.execute(SQL(
                """
                SELECT hv.sex, COUNT(hv.id)
                FROM hr_version hv, resource_calendar rc
                WHERE hv.id IN %(ids)s
                AND hv.resource_calendar_id = rc.id
                AND rc.hours_per_week = rc.full_time_required_hours
            GROUP BY hv.sex
                """,
                ids=version_ids,
            ))
            result = self.env.cr.dictfetchall()
            ft_count_per_gender = {
                item['sex']: item['count']
                for item in result
            }
            male_ft_count = ft_count_per_gender.get('male', 0)
            female_ft_count = ft_count_per_gender.get('female', 0)
            other_ft_count = ft_count_per_gender.get('other', 0)
            gender_not_reported_ft_count = ft_count_per_gender.get(None, 0)

            gender_data = get_gender_data(version_ids, total_employees_count)
            male_pt_count = gender_data['employees_male_count'] - male_ft_count
            female_pt_count = gender_data['employees_female_count'] - female_ft_count
            other_pt_count = gender_data['employees_other_count'] - other_ft_count
            gender_not_reported_pt_count = gender_data['employees_unknown_count'] - gender_not_reported_ft_count

            data.update({
                'male_ft_count': male_ft_count,
                'male_pt_count': male_pt_count,
                'female_ft_count': female_ft_count,
                'female_pt_count': female_pt_count,
                'other_ft_count': other_ft_count,
                'other_pt_count': other_pt_count,
                'gender_not_reported_ft_count': gender_not_reported_ft_count,
                'gender_not_reported_pt_count': gender_not_reported_pt_count
            })
            return data

        def get_non_salaried_data(version_ids):
            count_per_employee_type = dict(
                self.env['hr.version'].sudo()._read_group(
                    domain=[('id', 'in', version_ids)],
                    groupby=['employee_type_id'],
                    aggregates=['id:count'],
                )
            )
            return {
                'non_employees_non_salary_count': sum(
                    count_per_employee_type.get(emp_type, 0)
                    for emp_type in [self.env.ref('hr.contract_type_student'), self.env.ref('hr.contract_type_apprenticeship')]
                ),
                'non_employees_non_indep_count': sum(
                    count_per_employee_type.get(emp_type, 0)
                    for emp_type in [self.env.ref('hr.contract_type_seasonal'), self.env.ref('hr.contract_type_interim')]
                ),
                'non_employees_non_temp_count': count_per_employee_type.get('contract_type_intern', 0),
            }

        def get_gender_management_data(version_ids):
            if not version_ids:
                return []
            self.env.cr.execute(SQL(
                """
                WITH RECURSIVE leadership_level AS (
                    -- 1. Start with employees in the given versions
                    SELECT
                        e.id AS employee_id,
                        0 AS level,
                        ARRAY[e.id] AS visited_nodes,
                        hv.sex
                    FROM hr_employee e
                    JOIN hr_version hv ON e.id = hv.employee_id
                    WHERE hv.id IN %(ids)s

                    UNION ALL

                    -- 2. Move up the hierarchy
                    SELECT
                        e.parent_id AS employee_id,
                        lh.level + 1,
                        lh.visited_nodes || e.parent_id,
                        lh.sex -- Pass the gender of the original employee up the chain
                    FROM hr_employee e
                    JOIN leadership_level lh ON e.id = lh.employee_id
                    WHERE e.parent_id IS NOT NULL
                    AND NOT e.parent_id = ANY(lh.visited_nodes)
                ),
                max_levels AS (
                    -- 3. Calculate the maximum level reached for each employee version
                    SELECT
                        sex,
                        MAX(level) as max_lvl
                    FROM leadership_level
                GROUP BY employee_id, sex
                )
                -- 4. Count genders per level
                SELECT
                    max_lvl,
                    sex,
                    COUNT(*) as count
                FROM max_levels
            GROUP BY max_lvl, sex
            ORDER BY max_lvl DESC, sex;
                """,
                ids=tuple(version_ids)
            ))
            result = self.env.cr.dictfetchall()

            data = {}
            for item in result:
                lvl = item['max_lvl']
                gender = item['sex']
                count = item['count']
                if lvl not in data:
                    data[lvl] = {'male': 0, 'female': 0, 'other': 0}
                if gender:
                    data[lvl][gender] += count

            processed_data = []
            for lvl in sorted(data.keys(), reverse=True):
                stats = data[lvl]
                m = stats['male']
                f = stats['female']
                ratio = f / m if m > 0 else 0.0

                processed_data.append({
                    'level': lvl,
                    'male': m,
                    'female': f,
                    'other': stats['other'],
                    'ratio': round(ratio, 2)
                })
            return processed_data

        self.ensure_one()
        data = {}
        # Data for Employees
        # Reporting Year
        report_version_ids = get_valid_employee_version_ids(self.start_date, self.end_date, is_employee_type=True)
        report_total_employees_count = len(report_version_ids)
        data['total_reporting'] = str(report_total_employees_count)
        # Base Year
        base_total_employees_count = 0
        base_year_start_date = 0
        base_year_end_date = 0
        base_version_ids = False
        has_base_year = self._has_valid_base_year()
        if has_base_year:
            base_year_date = self.company_id.sudo().compute_fiscalyear_dates(date(self.base_year, 1, 1))
            base_year_start_date = base_year_date['date_from']
            base_year_end_date = base_year_date['date_to']
            base_version_ids = get_valid_employee_version_ids(base_year_start_date, base_year_end_date, is_employee_type=True)
            base_total_employees_count = len(base_version_ids)
            data['total_base'] = str(base_total_employees_count)

        # Data for Non-Employees
        # Reporting Year
        report_non_employees_version_ids = get_valid_employee_version_ids(self.start_date, self.end_date, is_employee_type=False)
        report_total_non_employees_count = len(report_non_employees_version_ids)
        data['total_non_employee_reporting'] = str(report_total_non_employees_count)
        # Base Year
        base_total_non_employees_count = 0
        base_non_employees_version_ids = False
        if has_base_year:
            base_non_employees_version_ids = get_valid_employee_version_ids(base_year_start_date, base_year_end_date, is_employee_type=False)
            base_total_non_employees_count = len(base_non_employees_version_ids)
            data['total_non_employee_base'] = str(base_total_non_employees_count)

        # Data for Employees + Non-Employees
        report_all_version_ids = get_valid_employee_version_ids(self.start_date, self.end_date)
        report_total_all_count = len(report_all_version_ids)

        # Regular template variables
        if not html_template_variables:

            # Data for Table: Employment Type
            # Reporting Year
            if report_version_ids and self.report_type == 'csrd':
                report_employment_type_result = get_employment_type_data(report_version_ids, report_total_employees_count)
                data.update({
                    'ft_reporting': str(report_employment_type_result['employees_full_time_count']),
                    'ft_pct_reporting': str(report_employment_type_result['employees_full_time_percentage']),
                    'pt_reporting': str(report_employment_type_result['employees_part_time_count']),
                    'pt_pct_reporting': str(report_employment_type_result['employees_part_time_percentage']),
                    'emp_type_not_reported_reporting': str(report_employment_type_result['employees_emp_type_not_reported_count']),
                    'emp_type_not_reported_pct_reporting': str(report_employment_type_result['employees_emp_type_not_reported_percentage']),
                })
            # Base Year
            if base_version_ids and self.report_type == 'csrd':
                base_employment_type_result = get_employment_type_data(base_version_ids, base_total_employees_count)
                data.update({
                    'ft_base': str(base_employment_type_result['employees_full_time_count']),
                    'ft_pct_base': str(base_employment_type_result['employees_full_time_percentage']),
                    'pt_base': str(base_employment_type_result['employees_part_time_count']),
                    'pt_pct_base': str(base_employment_type_result['employees_part_time_percentage']),
                    'emp_type_not_reported_base': str(base_employment_type_result['employees_emp_type_not_reported_count']),
                    'emp_type_not_reported_pct_base': str(base_employment_type_result['employees_emp_type_not_reported_percentage']),
                })

            # Data for Table: Gender
            # Reporting Year
            if report_version_ids:
                report_gender_result = get_gender_data(report_version_ids, report_total_employees_count)
                data.update({
                    'female_reporting': str(report_gender_result['employees_female_count']),
                    'female_pct_reporting': str(report_gender_result['employees_female_percentage']),
                    'male_reporting': str(report_gender_result['employees_male_count']),
                    'male_pct_reporting': str(report_gender_result['employees_male_percentage']),
                    'other_reporting': str(report_gender_result['employees_other_count']),
                    'other_pct_reporting': str(report_gender_result['employees_other_percentage']),
                    'gender_not_reported_reporting': str(report_gender_result['employees_unknown_count']),
                    'gender_not_reported_pct_reporting': str(report_gender_result['employees_unknown_percentage']),
                })
            # Base Year
            if base_version_ids:
                base_gender_result = get_gender_data(base_version_ids, base_total_employees_count)
                data.update({
                    'female_base': str(base_gender_result['employees_female_count']),
                    'female_pct_base': str(base_gender_result['employees_female_percentage']),
                    'male_base': str(base_gender_result['employees_male_count']),
                    'male_pct_base': str(base_gender_result['employees_male_percentage']),
                    'other_base': str(base_gender_result['employees_other_count']),
                    'other_pct_base': str(base_gender_result['employees_other_percentage']),
                    'gender_not_reported_base': str(base_gender_result['employees_unknown_count']),
                    'gender_not_reported_pct_base': str(base_gender_result['employees_unknown_percentage']),
                })

            # Data for Table: Age Group
            # Reporting Year
            if report_version_ids:
                report_age_group_result = get_age_group_data(report_version_ids, report_total_employees_count, self.end_date)
                data.update({
                    'age_lt30_reporting': str(report_age_group_result['employees_age_below_30_count']),
                    'age_lt30_pct_reporting': str(report_age_group_result['employees_age_below_30_percentage']),
                    'age_30_50_reporting': str(report_age_group_result['employees_age_between_30_and_50_count']),
                    'age_30_50_pct_reporting': str(report_age_group_result['employees_age_between_30_and_50_percentage']),
                    'age_gt50_reporting': str(report_age_group_result['employees_age_above_50_count']),
                    'age_gt50_pct_reporting': str(report_age_group_result['employees_age_above_50_percentage']),
                    'age_not_reported_reporting': str(report_age_group_result['employees_age_unknown_count']),
                    'age_not_reported_pct_reporting': str(report_age_group_result['employees_age_unknown_percentage']),
                })
            # Base Year
            if base_version_ids:
                base_age_group_result = get_age_group_data(base_version_ids, base_total_employees_count, base_year_end_date)
                data.update({
                    'age_lt30_base': str(base_age_group_result['employees_age_below_30_count']),
                    'age_lt30_pct_base': str(base_age_group_result['employees_age_below_30_percentage']),
                    'age_30_50_base': str(base_age_group_result['employees_age_between_30_and_50_count']),
                    'age_30_50_pct_base': str(base_age_group_result['employees_age_between_30_and_50_percentage']),
                    'age_gt50_base': str(base_age_group_result['employees_age_above_50_count']),
                    'age_gt50_pct_base': str(base_age_group_result['employees_age_above_50_percentage']),
                    'age_not_reported_base': str(base_age_group_result['employees_age_unknown_count']),
                    'age_not_reported_pct_base': str(base_age_group_result['employees_age_unknown_percentage']),
                })

            # Data for Table: Contract Type
            # Reporting Year
            if report_version_ids and self.report_type == 'csrd':
                report_contract_type_result = get_contract_type_data(report_version_ids, report_total_employees_count, self.start_date, self.end_date)
                data.update({
                    'permanent_reporting': str(report_contract_type_result['employees_permanent_contract_count']),
                    'permanent_pct_reporting': str(report_contract_type_result['employees_permanent_contract_percentage']),
                    'fixed_reporting': str(report_contract_type_result['employees_fixed_term_contract_count']),
                    'fixed_pct_reporting': str(report_contract_type_result['employees_fixed_term_contract_percentage']),
                    'contract_not_reported_reporting': str(report_contract_type_result['employees_unkown_contract_count']),
                    'contract_not_reported_pct_reporting': str(report_contract_type_result['employees_unkown_contract_percentage']),
                })
            # Base Year
            if base_version_ids and self.report_type == 'csrd':
                base_contract_type_result = get_contract_type_data(base_version_ids, base_total_employees_count, base_year_start_date, base_year_end_date)
                data.update({
                    'permanent_base': str(base_contract_type_result['employees_permanent_contract_count']),
                    'permanent_pct_base': str(base_contract_type_result['employees_permanent_contract_percentage']),
                    'fixed_base': str(base_contract_type_result['employees_fixed_term_contract_count']),
                    'fixed_pct_base': str(base_contract_type_result['employees_fixed_term_contract_percentage']),
                    'contract_not_reported_base': str(base_contract_type_result['employees_unkown_contract_count']),
                    'contract_not_reported_pct_base': str(base_contract_type_result['employees_unkown_contract_percentage']),
                })

            # Data for Table: Tenure
            # Reporting Year
            if report_version_ids and self.report_type == 'csrd':
                report_employee_tenure_result = get_employee_tenure_data(self.start_date, self.end_date, report_total_employees_count)
                data.update({
                    'tenure_lt1_reporting': str(report_employee_tenure_result['tenure_lt1']),
                    'tenure_lt1_pct_reporting': str(report_employee_tenure_result['tenure_lt1_pct']),
                    'tenure_1_3_reporting': str(report_employee_tenure_result['tenure_1_3']),
                    'tenure_1_3_pct_reporting': str(report_employee_tenure_result['tenure_1_3_pct']),
                    'tenure_3_5_reporting': str(report_employee_tenure_result['tenure_3_5']),
                    'tenure_3_5_pct_reporting': str(report_employee_tenure_result['tenure_3_5_pct']),
                    'tenure_gt5_reporting': str(report_employee_tenure_result['tenure_gt5']),
                    'tenure_gt5_pct_reporting': str(report_employee_tenure_result['tenure_gt5_pct']),
                    'tenure_not_reported_reporting': str(report_employee_tenure_result['tenure_not_reported']),
                    'tenure_not_reported_pct_reporting': str(report_employee_tenure_result['tenure_not_reported_pct']),
                })
            # Base Year
            if base_version_ids and self.report_type == 'csrd':
                base_employee_tenure_result = get_employee_tenure_data(base_year_start_date, base_year_end_date, base_total_employees_count)
                data.update({
                    'tenure_lt1_base': str(base_employee_tenure_result['tenure_lt1']),
                    'tenure_lt1_pct_base': str(base_employee_tenure_result['tenure_lt1_pct']),
                    'tenure_1_3_base': str(base_employee_tenure_result['tenure_1_3']),
                    'tenure_1_3_pct_base': str(base_employee_tenure_result['tenure_1_3_pct']),
                    'tenure_3_5_base': str(base_employee_tenure_result['tenure_3_5']),
                    'tenure_3_5_pct_base': str(base_employee_tenure_result['tenure_3_5_pct']),
                    'tenure_gt5_base': str(base_employee_tenure_result['tenure_gt5']),
                    'tenure_gt5_pct_base': str(base_employee_tenure_result['tenure_gt5_pct']),
                    'tenure_not_reported_base': str(base_employee_tenure_result['tenure_not_reported']),
                    'tenure_not_reported_pct_base': str(base_employee_tenure_result['tenure_not_reported_pct']),
                })

            # Data for Table: Employee Turnover
            # Reporting Year
            if report_version_ids:
                report_employee_turnover_result = get_employee_turnover_data(self.start_date, self.end_date)
                data.update({
                    'left_reporting': str(report_employee_turnover_result['leaving_employees_count']),
                    'avg_emp_reporting': str(report_employee_turnover_result['employees_avg_count']),
                    'turnover_reporting': str(report_employee_turnover_result['employees_turnover_rate']),
                })
            # Base Year
            if base_version_ids:
                base_employee_turnover_result = get_employee_turnover_data(base_year_start_date, base_year_end_date)
                data.update({
                    'left_base': str(base_employee_turnover_result['leaving_employees_count']),
                    'avg_emp_base': str(base_employee_turnover_result['employees_avg_count']),
                    'turnover_base': str(base_employee_turnover_result['employees_turnover_rate']),
                })

            # Data for Table: Workforce by Type of Contract
            # Reporting Year
            if report_version_ids and self.report_type != 'csrd':
                report_employment_type_per_gender_result = get_employment_type_per_gender_data(report_version_ids, report_total_employees_count)
                data.update({
                    'male_ft_reporting': str(report_employment_type_per_gender_result['male_ft_count']),
                    'male_pt_reporting': str(report_employment_type_per_gender_result['male_pt_count']),
                    'female_ft_reporting': str(report_employment_type_per_gender_result['female_ft_count']),
                    'female_pt_reporting': str(report_employment_type_per_gender_result['female_pt_count']),
                    'other_ft_reporting': str(report_employment_type_per_gender_result['other_ft_count']),
                    'other_pt_reporting': str(report_employment_type_per_gender_result['other_pt_count']),
                    'gender_not_reported_ft_reporting': str(report_employment_type_per_gender_result['gender_not_reported_ft_count']),
                    'gender_not_reported_pt_reporting': str(report_employment_type_per_gender_result['gender_not_reported_pt_count']),
                })
            # Base Year
            if base_version_ids and self.report_type != 'csrd':
                base_employment_type_per_gender_result = get_employment_type_per_gender_data(base_version_ids, base_total_employees_count)
                data.update({
                    'male_ft_base': str(base_employment_type_per_gender_result['male_ft_count']),
                    'male_pt_base': str(base_employment_type_per_gender_result['male_pt_count']),
                    'female_ft_base': str(base_employment_type_per_gender_result['female_ft_count']),
                    'female_pt_base': str(base_employment_type_per_gender_result['female_pt_count']),
                    'other_ft_base': str(base_employment_type_per_gender_result['other_ft_count']),
                    'other_pt_base': str(base_employment_type_per_gender_result['other_pt_count']),
                    'gender_not_reported_ft_base': str(base_employment_type_per_gender_result['gender_not_reported_ft_count']),
                    'gender_not_reported_pt_base': str(base_employment_type_per_gender_result['gender_not_reported_pt_count']),
                })

            # Data for Remuneration - Gender Pay Gap
            # Reporting Year
            if report_version_ids and self.report_type != 'csrd':
                report_pay_gap_result = get_pay_gap_data(report_version_ids)
                data.update({
                    'gender_pay_gap_reporting': str(report_pay_gap_result['pay_gap_percentage']),
                    'median_pay_male_reporting': str(report_pay_gap_result['male_median_hourly_salary']),
                    'median_pay_female_reporting': str(report_pay_gap_result['female_median_hourly_salary']),
                })
            # Base Year
            if base_version_ids and self.report_type != 'csrd':
                base_pay_gap_result = get_pay_gap_data(base_version_ids)
                data.update({
                    'gender_pay_gap_base': str(base_pay_gap_result['pay_gap_percentage']),
                    'median_pay_male_base': str(base_pay_gap_result['male_median_hourly_salary']),
                    'median_pay_female_base': str(base_pay_gap_result['female_median_hourly_salary']),
                })

            # Data for Table: Gender (Non-Employees)
            # Reporting Year
            if report_non_employees_version_ids and self.report_type == 'csrd':
                non_employees_report_gender_result = get_gender_data(report_non_employees_version_ids, report_total_non_employees_count)
                data.update({
                    'non_employee_female_reporting': str(non_employees_report_gender_result['employees_female_count']),
                    'non_employee_female_pct_reporting': str(non_employees_report_gender_result['employees_female_percentage']),
                    'non_employee_male_reporting': str(non_employees_report_gender_result['employees_male_count']),
                    'non_employee_male_pct_reporting': str(non_employees_report_gender_result['employees_male_percentage']),
                    'non_employee_other_reporting': str(non_employees_report_gender_result['employees_other_count']),
                    'non_employee_other_pct_reporting': str(non_employees_report_gender_result['employees_other_percentage']),
                    'non_employee_gender_not_reported_reporting': str(non_employees_report_gender_result['employees_unknown_count']),
                    'non_employee_gender_not_reported_pct_reporting': str(non_employees_report_gender_result['employees_unknown_percentage']),
                })
            # Base Year
            if base_non_employees_version_ids and self.report_type == 'csrd':
                non_employees_base_gender_result = get_gender_data(base_non_employees_version_ids, base_total_non_employees_count)
                data.update({
                    'non_employee_female_base': str(non_employees_base_gender_result['employees_female_count']),
                    'non_employee_female_pct_base': str(non_employees_base_gender_result['employees_female_percentage']),
                    'non_employee_male_base': str(non_employees_base_gender_result['employees_male_count']),
                    'non_employee_male_pct_base': str(non_employees_base_gender_result['employees_male_percentage']),
                    'non_employee_other_base': str(non_employees_base_gender_result['employees_other_count']),
                    'non_employee_other_pct_base': str(non_employees_base_gender_result['employees_other_percentage']),
                    'non_employee_gender_not_reported_base': str(non_employees_base_gender_result['employees_unknown_count']),
                    'non_employee_gender_not_reported_pct_base': str(non_employees_base_gender_result['employees_unknown_percentage']),
                })

            # Data for Table: B8.5: Non-Employees
            # Reporting Year
            if report_non_employees_version_ids and self.report_type != 'csrd':
                non_employees_report_non_salaried_result = get_non_salaried_data(report_non_employees_version_ids)
                data.update({
                    'non_salary_reporting': str(non_employees_report_non_salaried_result['non_employees_non_salary_count']),
                    'non_indep_reporting': str(non_employees_report_non_salaried_result['non_employees_non_indep_count']),
                    'non_temp_reporting': str(non_employees_report_non_salaried_result['non_employees_non_temp_count']),
                })
            # Base Year
            if base_non_employees_version_ids and self.report_type != 'csrd':
                non_employees_base_non_salaried_result = get_non_salaried_data(base_non_employees_version_ids)
                data.update({
                    'non_salary_base': str(non_employees_base_non_salaried_result['non_employees_non_salary_count']),
                    'non_indep_base': str(non_employees_base_non_salaried_result['non_employees_non_indep_count']),
                    'non_temp_base': str(non_employees_base_non_salaried_result['non_employees_non_temp_count']),
                })

            # Data for Table: Diversity Metrics (Employees + Non-Employees)
            # Reporting Year
            if report_all_version_ids and self.report_type == 'csrd':
                report_gender_result = get_gender_data(report_all_version_ids, report_total_all_count)
                data.update({
                    'women_workforce_pct_reporting': str(report_gender_result['employees_female_percentage']),
                })
                report_age_group_result = get_age_group_data(report_all_version_ids, report_total_all_count, self.end_date)
                data.update({
                    'employees_lt30_pct_reporting': str(report_age_group_result['employees_age_below_30_percentage']),
                    'employees_gt50_pct_reporting': str(report_age_group_result['employees_age_above_50_percentage']),
                })
                report_gender_management_data = get_gender_management_data(report_all_version_ids)
                if report_gender_management_data:
                    total = report_gender_management_data[0]['female'] + report_gender_management_data[0]['male']
                    data['women_management_pct_reporting'] = str(round((report_gender_management_data[0]['female'] / total) * 100, 2)) if total > 0 else '0.0'

        # HTML template variables
        else:
            # Data for Table: Geography/Region (Employees)
            if report_version_ids:
                # Reporting Year
                data['country_employees_report_data'] = get_country_employees_data(report_version_ids)
                # Base Year
                data['country_employees_base_data'] = get_country_employees_data(base_version_ids)

            # Data for Table: Job Category/Function (Employees)
            if report_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['department_employees_report_data'] = get_department_employees_data(report_version_ids)
                # Base Year
                data['department_employees_base_data'] = get_department_employees_data(base_version_ids)

            # Data for Table: Employment Type (Non-Employees)
            if report_non_employees_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['report_non_employee_type_data'] = get_employee_type_data(report_non_employees_version_ids)
                # Base Year
                data['base_non_employee_type_data'] = get_employee_type_data(base_non_employees_version_ids)

            # Data for Table: Geography/Region (Non-Employees)
            if report_non_employees_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['report_non_employee_country_data'] = get_country_employees_data(report_non_employees_version_ids)
                # Base Year
                data['base_non_employee_country_data'] = get_country_employees_data(base_non_employees_version_ids)

            # Data for Table: Job Category/Function (Non-Employees)
            if report_non_employees_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['report_non_employee_department_data'] = get_department_employees_data(report_non_employees_version_ids)
                # Base Year
                data['base_non_employee_department_data'] = get_department_employees_data(base_non_employees_version_ids)

            # Data for Tables: Remuneration Metrics
            # Data for Table: Job Category/Function Pay Gap (Employees + Non-Employees)
            if report_all_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['report_department_pay_gap_data'] = get_department_pay_gap_data(report_all_version_ids)

            # Data for Table: Contract Type Pay Gap (Employees + Non-Employees)
            if report_all_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['report_contract_pay_gap_data'] = get_contract_type_pay_gap_data(report_all_version_ids)

            # Data for Table: Country Pay Gap (Employees + Non-Employees)
            if report_all_version_ids and self.report_type == 'csrd':
                # Reporting Year
                data['report_country_pay_gap_data'] = get_country_pay_gap_data(report_all_version_ids)

            # Gender Ratio at Management Level (Employees + Non-Employees)
            if report_all_version_ids and self.report_type != 'csrd':
                # Reporting Year
                data['report_gender_management_data'] = get_gender_management_data(report_all_version_ids)

        return data
