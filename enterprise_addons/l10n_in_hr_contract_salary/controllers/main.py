# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo.addons.hr_contract_salary.utils.hr_version import hr_version_context
from odoo.addons.hr_contract_salary.controllers.main import HrContractSalary
from odoo.http import request
from odoo.tools import float_is_zero, float_round
from odoo.tools.float_utils import float_compare


class L10nInHrContractSalary(HrContractSalary):

    def _get_new_version_values(self, version, employee, benefits, offer):
        if offer.country_code != 'IN':
            return super()._get_new_version_values(version, employee, benefits, offer)
        benefits = dict(benefits)
        if not offer.company_id.l10n_in_provident_fund:
            benefits.setdefault('l10n_in_pf_employee_amount', 0.0)
        res = super()._get_new_version_values(version, employee, benefits, offer)
        fields_to_copy = [
            'l10n_in_hra_percentage', 'l10n_in_fixed_allowance', 'l10n_in_gratuity',
            'l10n_in_lwf_employee_contribution', 'l10n_in_lwf_employer_contribution', 'l10n_in_esic_employee_amount',
            'l10n_in_leave_travel_allowance', 'l10n_in_basic_salary_amount',
            'l10n_in_standard_allowance', 'l10n_in_performance_bonus', 'l10n_in_professional_tax',
            'l10n_in_pf_enabled', 'l10n_in_pf_employee_type', 'l10n_in_pf_employer_type'
        ]
        for field_to_copy in fields_to_copy:
            if field_to_copy in benefits:
                res[field_to_copy] = benefits[field_to_copy]
            elif field_to_copy in version:
                res[field_to_copy] = version[field_to_copy]

        pf_radio_key = 'l10n_in_pf_employee_amount_radio'
        if pf_radio_key in benefits:
            pf_enabled = bool(float(benefits.get(pf_radio_key) or 0.0))
            res['l10n_in_pf_enabled'] = pf_enabled
            if not pf_enabled:
                res.update({
                    'l10n_in_pf_employee_type': False,
                    'l10n_in_pf_employer_type': False,
                    'l10n_in_pf_employer_amount': 0.0,
                })
        elif not res.get('l10n_in_pf_enabled'):
            res.update({
                'l10n_in_pf_employee_type': False,
                'l10n_in_pf_employer_type': False,
                'l10n_in_pf_employer_amount': 0.0,
            })
        return res

    def create_new_version(self, version_vals, offer, benefits, no_write=False, **kw):
        new_version, version_diff = super().create_new_version(version_vals, offer, benefits, no_write=no_write, **kw)
        if offer.country_code != 'IN':
            return new_version, version_diff
        original_wage = version_vals.get('wage')
        if original_wage is not None:
            new_version.wage = original_wage
        benefits_adv = benefits['version']
        new_version.write({
            'l10n_in_insured_spouse': benefits_adv.get('fold_l10n_in_insured_spouse', False),
            'l10n_in_insured_first_children': benefits_adv.get('fold_l10n_in_insured_first_children', False),
            'l10n_in_insured_second_children': benefits_adv.get('fold_l10n_in_insured_second_children', False),
        })
        if kw.get('package_submit'):
            with hr_version_context(new_version) as new_version:
                payslip = new_version._generate_salary_simulation_payslip()
                net_total = sum(line['total'] for line in payslip._get_payslip_lines() if line['code'] == 'NET')

            if float_compare(net_total, 0.0, precision_digits=2) < 0:
                new_version.unlink()
                return {
                    'error': 1,
                    'error_msg': self.env._(
                        'Net salary cannot be negative. Please reduce benefits or increase employer cost.'
                    ),
                }
        return new_version, version_diff

    def _get_benefits_values(self, version, offer):
        mapped_benefits, mapped_dependent_benefits, mapped_mandatory_benefits, mapped_mandatory_benefits_names,\
            benefit_types, dropdown_options, dropdown_group_options, initial_values =\
            super()._get_benefits_values(version, offer)
        if not version.l10n_in_provident_fund:
            mapped_benefits = {
                benefit_type: filtered_benefits
                for benefit_type, benefits in mapped_benefits.items()
                if (filtered_benefits := benefits.filtered(lambda benefit: benefit.field != 'l10n_in_pf_employee_amount'))
            }
            benefit_types = [benefit_type for benefit_type in benefit_types if benefit_type in mapped_benefits]
            initial_values.pop('l10n_in_pf_employee_amount', None)

        benefit_fields = [
            'l10n_in_insured_spouse', 'l10n_in_insured_first_children', 'l10n_in_insured_second_children'
        ]
        for benefit in benefit_fields:
            if initial_values.get(benefit):
                initial_values[benefit] = version.l10n_in_medical_insurance

        return mapped_benefits, mapped_dependent_benefits, mapped_mandatory_benefits, mapped_mandatory_benefits_names,\
            benefit_types, dropdown_options, dropdown_group_options, initial_values

    def _compute_onchange_benefit(self, version, benefit_field, new_value, offer, benefits, **kw):
        res = super()._compute_onchange_benefit(version, benefit_field, new_value, offer, benefits, **kw)
        benefit_fields = [
            'l10n_in_pf_employee_amount', 'l10n_in_medical_insurance', 'l10n_in_phone_subscription',
            'l10n_in_internet_subscription', 'l10n_in_meal_voucher_amount', 'l10n_in_company_transport'
        ]
        fold_benefit_fields = [
            'fold_l10n_in_insured_spouse', 'fold_l10n_in_insured_first_children', 'fold_l10n_in_insured_second_children'
        ]

        if benefit_field in benefit_fields:
            if benefit_field == 'l10n_in_pf_employee_amount' and not float(new_value or 0.0):
                res['new_value'] = ''
            else:
                res['new_value'] = str(version[benefit_field]) if float(new_value or 0.0) else 0
        elif benefit_field in fold_benefit_fields:
            current_insurance = benefits['version'].get('l10n_in_medical_insurance')
            if current_insurance is None:
                current_insurance = version.l10n_in_medical_insurance
            current_insurance = float(current_insurance or 0.0)
            res['extra_values'] = [
                (benefit_field.replace('fold_', ''), current_insurance if benefits['version'].get(benefit_field) else 0)
            ]
        return res

    def _get_compute_results(self, new_version):
        result = super()._get_compute_results(new_version)

        if new_version.company_id.country_id != self.env.ref('base.in'):
            return result
        monthly_salary_name = request.env.ref(
            'hr_contract_salary.hr_contract_salary_resume_category_monthly_salary').name
        monthly_salary_lines = result['resume_lines_mapped'].get(monthly_salary_name, {})
        wage_amount_to_remove = 0.0
        if 'GROSS' in monthly_salary_lines and (generic_wage_line := monthly_salary_lines.pop('wage', None)):
            generic_wage_record = request.env['hr.contract.salary.resume'].sudo().with_company(new_version.company_id).search([
                ('code', '=', 'wage'),
                ('structure_type_id', '=', False),
            ], limit=1)
            if generic_wage_record.impacts_monthly_total:
                wage_amount_to_remove = generic_wage_line[1]

        offer = request.env['hr.contract.salary.offer']
        dependents_selected, additional_cover_amount = offer._l10n_in_get_medical_insurance_dependents(new_version)
        difference = float_round(additional_cover_amount - dependents_selected, precision_digits=2) if dependents_selected else 0.0
        total_adjustment = float_round(difference - wage_amount_to_remove, precision_digits=2)
        if float_is_zero(difference, precision_digits=2) and float_is_zero(wage_amount_to_remove, precision_digits=2):
            return result

        # Adjust the Monthly Benefits resume line so dependent coverage reflects its real cost.
        for category, lines in result['resume_lines_mapped'].items():
            if 'monthly_benefits' in lines:
                name, current_value, symbol, explanation, currency_position, uom_code = lines['monthly_benefits']
                lines['monthly_benefits'] = (
                    name,
                    float_round(current_value + difference, precision_digits=2),
                    symbol,
                    explanation,
                    currency_position,
                    uom_code,
                )
                break

        # Keep monthly total lines aligned with the adjusted benefits value.
        monthly_total_lines = request.env['hr.contract.salary.resume'].sudo().with_company(new_version.company_id).search([
            ('value_type', '=', 'monthly_total'),
            '|',
                ('structure_type_id', '=', False),
                ('structure_type_id', '=', new_version.structure_type_id.id),
        ])
        for resume_line in monthly_total_lines:
            category_lines = result['resume_lines_mapped'].get(resume_line.category_id.name)
            if not category_lines:
                continue
            key = resume_line.code if resume_line.code in category_lines else False
            if key not in category_lines:
                continue
            name, current_value, symbol, explanation, currency_position, uom_code = category_lines[key]
            category_lines[key] = (
                name,
                float_round(current_value + total_adjustment, precision_digits=2),
                symbol,
                explanation,
                currency_position,
                uom_code,
            )

        return result

    def _compute_update_salary(self, version, offer, benefits, **kw):
        result = super()._compute_update_salary(version, offer, benefits, **kw)
        if offer.country_code != 'IN':
            return result
        net_total = 0.0
        for lines in result.get('resume_lines_mapped', {}).values():
            if 'NET' in lines:
                net_total = lines['NET'][1]
                break
        if float_compare(net_total, 0.0, precision_digits=2) < 0:
            result['configurator_warning'] = self.env._(
                'Net salary cannot be negative. Please reduce benefits or increase employer cost.'
            )
        return result

    def _update_personal_info(self, employee, version, personal_infos_values, no_name_write=False):
        unique_statutory_fields = {'l10n_in_uan', 'l10n_in_pan', 'l10n_in_esic_number'}
        employee_infos = personal_infos_values.get('employee', {})
        if employee_infos:
            for field in unique_statutory_fields:
                if not employee_infos.get(field):
                    employee_infos[field] = None
        return super()._update_personal_info(
            employee, version, personal_infos_values, no_name_write=no_name_write
        )
