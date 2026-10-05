# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date
import logging
import re

from lxml import etree
from markupsafe import Markup
from stdnum.be.vat import compact as vat_be_compact

from odoo import api, fields, models
from odoo.fields import Domain
from odoo.addons.l10n_be_hr_payroll.models.l10n_be_281_XX import COUNTRY_CODES
from odoo.exceptions import UserError
from odoo.tools import float_round
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

# Sources:
# - Technical Doc https://finances.belgium.be/fr/E-services/Belcotaxonweb/documentation-technique
# - "Avis aux débiteurs" https://finances.belgium.be/fr/entreprises/personnel_et_remuneration/avis_aux_debiteurs#q2


class L10n_Be281_Mixin(models.AbstractModel):
    _name = 'l10n_be.281.mixin'
    _inherit = ['hr.payroll.declaration.mixin']
    _description = 'HR Payroll 281 Declaration Mixin'

    declaration_id = fields.Many2one('l10n_be.281_xx', index=True, ondelete='cascade')

    def _country_restriction(self):
        return 'BE'

    def _get_lang_code(self, lang):
        return self.declaration_id._get_lang_code(lang)

    def _get_country_code(self, country):
        return self.declaration_id._get_country_code(country)

    @api.model
    def _check_employees_configuration(self, employees):
        invalid_employees = employees.filtered(lambda e: not (e.company_id and e.company_id.street and e.company_id.zip and e.company_id.city and e.company_id.phone and e.company_id.vat))
        if invalid_employees:
            raise UserError(self.env._("The company is not correctly configured on your employees. Please be sure that the following pieces of information are set: street, zip, city, phone and vat") + '\n' + '\n'.join(invalid_employees.mapped('name')))

        invalid_employees = employees.filtered(
            lambda e: not e.private_street or not e.private_zip or not e.private_city or not e.private_country_id)
        if invalid_employees:
            raise UserError(self.env._("The following employees don't have a valid private address (with a street, a zip, a city and a country):\n%s", '\n'.join(invalid_employees.mapped('name'))))

        invalid_employees = employees.filtered(lambda emp: not emp.version_ids or not emp.version_id)
        if invalid_employees:
            raise UserError(self.env._('Some employee has no contract:\n%s', '\n'.join(invalid_employees.mapped('name'))))

        invalid_employees = employees.filtered(lambda e: e.l10n_be_dimona_category != 'alt' and not e._is_niss_valid())
        if invalid_employees:
            raise UserError(self.env._('Invalid NISS number for those employees:\n %s', '\n'.join(invalid_employees.mapped('name'))))

        invalid_employees = employees.filtered(lambda e: not e.l10n_be_legal_first_name or not e.l10n_be_legal_last_name)
        if invalid_employees:
            raise UserError(self.env._("The following employees don't have a legal first and last name defined:\n %s", '\n'.join(invalid_employees.mapped('name'))))

        invalid_country_codes = employees.private_country_id.filtered(lambda c: c.code not in COUNTRY_CODES)
        if invalid_country_codes:
            raise UserError(self.env._('Unsupported country code %s. Please contact an administrator.', ', '.join(invalid_country_codes.mapped('code'))))

    def _get_declaration_period(self):
        year = int(self.declaration_id.year)
        return date(year, 1, 1), date(year, 12, 31)

    def _get_fiscal_line_domain(self):
        return self.env['hr.payslip']._l10n_be_get_fiscal_line_domain(*self._get_declaration_period())

    def action_generate_declarations(self):
        self.line_ids.unlink()
        for sheet in self:
            company_id = sheet.declaration_id.company_id
            all_payslips = self.env['hr.payslip'].search(Domain([
                ('state', 'in', ['validated', 'paid']),
                ('company_id', '=', company_id.id),
                ('employee_id.l10n_be_dimona_category', '!=', 'alt'),
            ]) & self.env['hr.payslip']._l10n_be_get_fiscal_period_domain(*sheet._get_declaration_period()))
            payslips = all_payslips.filtered(lambda p: not p.version_id.no_withholding_taxes)
            sheet.declaration_id.payslip_ids |= payslips
            sheet.declaration_id.untaxed_employee_ids = (all_payslips - payslips).employee_id
            eligible_employees = self._get_eligible_employees(payslips)
            sheet.write({
                'line_ids': [(0, 0, {
                    'employee_id': employee.id,
                    'res_model': self._name,
                    'res_id': sheet.id,
                }) for employee in eligible_employees]
            })
        return True

    def _get_rendering_data(self, employees):
        self.ensure_one()
        self.declaration_id._check_company_configuration()

        all_payslips = self.env['hr.payslip'].search(Domain([
            ('state', 'in', ['validated', 'paid']),
            ('employee_id', 'in', employees.ids),
        ]) & self.env['hr.payslip']._l10n_be_get_fiscal_period_domain(*self._get_declaration_period()))
        all_employees = all_payslips.employee_id
        self._check_employees_configuration(all_employees)

        line_codes = self._get_line_codes()
        all_line_values = all_payslips._get_line_values(
            line_codes, vals_list=['total', 'quantity'], extra_domain=self._get_fiscal_line_domain())
        employee_payslips = all_payslips.grouped('employee_id')
        return self._generate_employees_data(employee_payslips, all_line_values)

    def _get_eligible_employees(self, payslips):
        # Return employees that should be included in the declaration.
        return payslips.employee_id

    def _to_eurocent(self, amount):
        # Convert amount to eurocents if context requires it.
        round_281 = self.env.context.get('round_281')
        return int(amount * 100) if round_281 else amount

    def _get_line_codes(self):
        return list(set(self.env['hr.salary.rule'].with_context(active_test=False).search([]).mapped('code')))

    def _get_declaration_code(self):
        raise NotImplementedError("Child models must define their declaration code.")

    def _get_mapping_lines(self, year):
        self.ensure_one()
        return self.env['l10n.be.281.mapping'].search([
            ('declaration_code', '=', self._get_declaration_code()),
            ('date_from', '<=', date(int(year), 1, 1)),
            '|', ('date_to', '=', False), ('date_to', '>=', date(int(year), 12, 31)),
        ])

    def _generate_employees_data(self, employee_payslips, all_line_values):
        self.ensure_one()
        base_employees_data = {}
        employees_with_error = {}
        sequence = self.env.context.get('starting_sequence', 0)
        for employee in employee_payslips:
            is_belgium = employee.private_country_id.code == 'BE'
            sequence += 1

            postcode = employee.private_zip.strip() if is_belgium else '0'
            if len(postcode) > 4 or not postcode.isdecimal():
                employees_with_error[employee] = self.env._("The belgian postcode length shouldn't exceed 4 characters and should contain only numbers for employee %s", employee.name)
                continue

            names = re.sub(r"\([^()]*\)", "", employee.name).strip().split()
            first_name = names[-1]
            last_name = ' '.join(names[:-1])
            if len(first_name) > 30:
                employees_with_error[employee] = self.env._("The employee first name shouldn't exceed 30 characters for employee %s", employee.name)
                continue

            first_contract_date = employee._get_first_contract_date(date_limit=date(int(self.declaration_id.year), 12, 31))
            if not first_contract_date:
                employees_with_error[employee] = self.env._("No first contract date found for employee %s", employee.name)
                continue

            sheet_values = {
                'employee': employee,
                'employee_id': employee.id,
                'entry_date': first_contract_date.strftime('%d-%m-%Y'),
                'departure_date': employee.departure_date.strftime('%d-%m-%Y') if employee.departure_date and employee.departure_date > first_contract_date else '',
                'f2002_inkomstenjaar': self.declaration_id.year,
                'f2005_registratienummer': vat_be_compact(self.declaration_id.company_id.vat),
                'f2008_typefiche': self._get_declaration_code().replace('.', ''),
                'f2009_volgnummer': sequence,
                'f2011_nationaalnr': employee.niss,
                'f2013_naam': last_name,
                'f2015_adres': employee.private_street,
                'f2016_postcodebelgisch': postcode,
                'employee_city': employee.private_city,
                'f2018_landwoonplaats': '150' if is_belgium else self._get_country_code(employee.private_country_id),
                'f2027_taalcode': self._get_lang_code(employee.lang),
                'f2028_typetraitement': self.declaration_id.type_treatment,
                'f2029_enkelopgave325': 0,
                'f2112_buitenlandspostnummer': employee.private_zip if not is_belgium else '0',
                'f2114_voornamen': first_name,
            }

            # Le code postal belge (2016) et le code postal étranger (2112) ne peuvent jamais être remplis tous les deux.
            # Ils ne peuvent pas non plus être vides tous les deux.
            if is_belgium:
                sheet_values.pop('f2112_buitenlandspostnummer')
            else:
                sheet_values.pop('f2016_postcodebelgisch')

            base_employees_data[employee] = sheet_values

        sum_2009 = sum(sheet_values['f2009_volgnummer'] for sheet_values in base_employees_data.values())

        year = self.declaration_id.year
        mapping_lines = self._get_mapping_lines(year)
        line_codes = self._get_line_codes()
        employees_data = []
        for employee, payslips in employee_payslips.items():
            if employee not in base_employees_data:
                continue
            line_values = {
                code: sum(all_line_values[code][p.id]['total'] for p in payslips)
                for code in line_codes
            }
            sheet_values = self._get_declaration_data(mapping_lines, line_values)
            employees_data.append({**base_employees_data[employee], **sheet_values})

        control_tags = mapping_lines.filtered(lambda mapping_line: mapping_line.evaluation_type == 'control').mapped('tag')
        sum_control_total = sum(
            sheet_values[tag] for sheet_values in employees_data for tag in control_tags
        )

        return {
            'base_employees_data': base_employees_data,
            'employees_data': employees_data,
            'employees_with_error': employees_with_error,
            'sum_volgnummer': sum_2009,
            'sum_control_total': sum_control_total,
            'sum_withholding': 0,
            'mapping_lines': mapping_lines,
        }

    def _post_process_rendering_data_pdf(self, rendering_data):
        result = {}
        data = self.declaration_id._get_main_data()
        for sheet_values in rendering_data['employees_data']:
            for key, value in sheet_values.items():
                if isinstance(value, int) and value == 0:
                    sheet_values[key] = '0.00 €'
                elif isinstance(value, float):
                    sheet_values[key] = f'{value:,.2f} €'
                elif not value:
                    sheet_values[key] = self.env._('None')
            result[sheet_values['employee']] = {**sheet_values, **data}
        return result

    def _get_localdict(self):
        return {"float_round": float_round, "_to_eurocent": self._to_eurocent}

    def _get_declaration_data(self, mapping_lines, line_values):
        self.ensure_one()
        mapping_lines = mapping_lines.sorted(key=lambda mapping_line: mapping_line.evaluation_type == 'control')

        computed = {}
        for mapping_line in mapping_lines:
            computed[mapping_line.tag] = self._evaluate(mapping_line, line_values, computed)
        return computed

    def _evaluate(self, mapping_line, line_values, computed):
        if mapping_line.evaluation_type == 'salary_rule':
            return self._evaluate_salary_rule(mapping_line, line_values)
        if mapping_line.evaluation_type == 'python':
            return self._evaluate_python(mapping_line, line_values)
        if mapping_line.evaluation_type == 'control':
            return self._evaluate_control(mapping_line, computed)
        raise UserError(self.env._(
            "l10n.be.281.mapping row %(tag)s has unsupported evaluation type %(type)s.",
            tag=mapping_line.tag, type=mapping_line.evaluation_type,
        ))

    def _evaluate_salary_rule(self, mapping_line, line_values):
        total = sum(line_values[code] for code in mapping_line._get_codes())
        return self._to_eurocent(round(total, 2))

    def _evaluate_python(self, mapping_line, line_values):
        localdict = self._get_localdict()
        localdict['mapped_total'] = dict(line_values)
        try:
            # PY001: evaluation_value is writable only by group_hr_payroll_manager.
            # That's the same trust level as hr.salary.rule's condition_python/amount_python_compute.
            safe_eval(mapping_line.evaluation_value, localdict, mode='exec')
        except Exception as e:
            raise UserError(self.env._(
                "l10n.be.281.mapping row %(tag)s failed to evaluate %(expr)s: %(error)s",
                tag=mapping_line.tag, expr=mapping_line.evaluation_value, error=e,
            )) from e
        if 'result' not in localdict:
            raise UserError(self.env._(
                "l10n.be.281.mapping row %(tag)s: python evaluation_value must assign a 'result' variable.",
                tag=mapping_line.tag,
            ))
        result = localdict['result']
        return self._to_eurocent(round(result, 2)) if mapping_line.is_monetary else result

    def _evaluate_control(self, mapping_line, computed):
        total = 0
        for target in mapping_line.control_mapping_ids:
            try:
                total += computed[target.tag]
            except KeyError as e:
                raise UserError(self.env._(
                    "l10n.be.281.mapping control row %(tag)s references unknown or not-yet-computed tag %(missing)s.",
                    tag=mapping_line.tag, missing=e.args[0],
                )) from e
        return total

    def _get_xml_declaration_fields_markup(self, employee_data, lines):
        # Built with lxml, not a QWeb t-foreach: QWeb can't set an element's tag name dynamically.
        self.ensure_one()
        skip_if_falsy_tags = set(lines.filtered('skip_if_falsy').mapped('tag'))
        tags = sorted(lines.mapped('tag'), key=lambda tag: int(tag.split('_')[1]))
        root = etree.Element('root')
        for tag in tags:
            value = employee_data[tag]
            if tag in skip_if_falsy_tags and not value:
                continue
            etree.SubElement(root, tag).text = str(value)
        # PY014: lxml's tostring already XML-escapes this text, so Markup wraps escaped content, not raw.
        return Markup('').join(
            Markup(etree.tostring(child, encoding='unicode')) for child in root
        )
