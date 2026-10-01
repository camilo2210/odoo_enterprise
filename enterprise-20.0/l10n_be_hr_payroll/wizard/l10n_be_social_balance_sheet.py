# Part of Odoo. See LICENSE file for full copyright and licensing details.

import collections
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import BinaryBytes
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class L10nBeSocialBalanceSheet(models.TransientModel):
    _name = 'l10n.be.social.balance.sheet'
    _description = 'Belgium: Social Balance Sheet'

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "BE":
            raise UserError(self.env._('This feature seems to be as exclusive as Belgian chocolates. You must be logged in to a Belgian company to use it.'))
        return super().default_get(fields)

    def _get_default_company_id(self):
        return self.env.company if not self.env.company.parent_id else False

    # Source: https://www.nbb.be/fr/centrale-des-bilans/etablir-et-deposer/que-faut-il-deposer/modeles/modeles-pour-societes
    # Introduction: https://www.nbb.be/doc/ba/models/social%20balance/avis_cnc_2009_12.pdf
    # Q&A about social balance sheet: https://www.nbb.be/doc/ba/models/social%20balance/avis_cnc_s100.pdf
    # Explanations about trainings: https://www.nbb.be/doc/ba/models/social%20balance/avis_cnc_2009_12.pdf
    # Blank complete scheme example: https://www.nbb.be/doc/ba/models/ent/2023/standaardmodellen/release_2021_fr_modele_c_societes_a_capital_v8.pdf

    date_from = fields.Date(default=lambda s: fields.Date.context_today(s) + relativedelta(day=1, month=1, years=-1))
    date_to = fields.Date(default=lambda s: fields.Date.context_today(s) + relativedelta(day=31, month=12, years=-1))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
    ], default='draft')
    social_balance_sheet = fields.Binary('Social Balance Sheet', readonly=True, attachment=False)
    company_id = fields.Many2one(
        "res.company",
        domain="[('parent_id', '=', False)]",
        default=_get_default_company_id,
        required=True,
    )
    branch_ids = fields.Many2many("res.company", compute="_compute_branch_ids")
    social_balance_filename = fields.Char()

    @api.depends('company_id')
    def _compute_branch_ids(self):
        report_companies = self.mapped('company_id')
        branches_by_root = self.env['res.company'].search([
            ('id', 'child_of', report_companies.ids),
        ]).grouped('root_id')

        for report in self:
            report.branch_ids = branches_by_root.get(report.company_id, report.company_id)

    def _get_report_data(self):
        def _get_contract_type_code(contract, replacement, defined_work):
            if contract.employee_type_id == replacement:
                return '113'
            if contract.employee_type_id == defined_work:
                return '112'
            if contract.fixed_term:
                return '111'  # CDD
            return '110'  # CDI

        def _get_in_out_contract_type_code(contract, replacement, defined_work):
            if contract.employee_type_id == replacement:
                return '213', '313'
            if contract.employee_type_id == defined_work:
                return '212', '312'
            if contract.fixed_term:
                return '211', '311'  # CDD
            return '210', '310'  # CDI

        self.ensure_one()
        contracts = self.env['hr.employee']._get_all_versions_with_contract_overlap_with_period(self.date_from, self.date_to)
        contracts = contracts.filtered(lambda c: c.l10n_be_joint_committee_id.egov3_code != '999')
        invalid_employees = contracts.employee_id.filtered(lambda e: e.slip_ids and e.sex not in ['male', 'female'])
        if invalid_employees:
            raise UserError(self.env._('Please configure a sex (either male or female) for the following employees:\n\n%s', '\n'.join(invalid_employees.mapped('name'))))

        report_data = {}

        payslips = self.env['hr.payslip'].search([
            ('state', 'in', ['validated', 'paid']),
            ('struct_id.type_id', '=', self.env.ref('hr.structure_type_employee_cp200').id),
            ('company_id', 'in', self.branch_ids.ids),
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('version_id.l10n_be_worker_code_id.dmfa_code', 'not in', ['848', '849']),
            ])

        # SECTION 100
        # Calculated as the average of number of workers entered in the personnel register at
        # the end of each month of the accounting year.

        # 2 payslips on different working rate on the same month should be treated
        # specifically
        mapped_payslips = collections.defaultdict(lambda: self.env['hr.payslip'])
        for payslip in payslips:
            period = (payslip.date_from.month, payslip.date_from.year, payslip.employee_id.id)
            mapped_payslips[period] |= payslip

        workers_data = collections.defaultdict(lambda: dict(full=0, part=0, fte=0))

        for employee_payslips in mapped_payslips.values():
            if len(employee_payslips) > 1:
                # What matters is the occupation at the end of the month. Take the most recent contract
                payslip = employee_payslips.sorted(lambda p: p.version_id.date_start, reverse=True)[-1]
            else:
                payslip = employee_payslips
            version = payslip.version_id
            sex = version.sex
            if version.work_time_rate >= 1:
                workers_data[sex]['full'] += 1
                workers_data[sex]['fte'] += 1
            else:
                workers_data[sex]['part'] += 1
                workers_data[sex]['fte'] += 1 * version.work_time_rate

        report_data.update({
            '1001_male': round(workers_data['male']['full'] / 12.0, 2),
            '1001_female': round(workers_data['female']['full'] / 12.0, 2),
            '1001_total': round((workers_data['male']['full'] + workers_data['female']['full']) / 12.0, 2),
            '1002_male': round(workers_data['male']['part'] / 12.0, 2),
            '1002_female': round(workers_data['female']['part'] / 12.0, 2),
            '1002_total': round((workers_data['male']['part'] + workers_data['female']['part']) / 12.0, 2),
            '1003_male': round(workers_data['male']['fte'] / 12.0, 2),
            '1003_female': round(workers_data['female']['fte'] / 12.0, 2),
            '1003_total': round((workers_data['male']['fte'] + workers_data['female']['fte']) / 12.0, 2),
        })

        # SECTION 101
        # The methodological notice concerning the social report published in the Belgian Official
        # Gazette (Moniteur belge) of August 30, 1996 specifies that the actual number of hours
        # worked (item 101) includes: "the total hours actually worked performed and paid during
        # the year; that is to say without take into account unpaid overtime (62), vacation, sick
        # leave, absences of short duration (63) and hours lost due to strike or for any other
        # reason ”.
        # This definition is directly followed by the description of what is meant by number of
        # hours worked on the basis of the quarterly declaration to the ONSS. This way to proceed
        # may lead to an overestimation of the hours of work actually performed. Indeed, the
        # ONSS takes into account the hours or days not worked but assimilated (64) to working days
        # to determine the employee benefits.
        workers_data = collections.defaultdict(lambda: dict(full=0, part=0, fte=0))

        for payslip in payslips:
            version = payslip.version_id
            sex = version.sex
            lines = payslip.worked_days_line_ids.filtered_domain([
                ('is_paid', '=', True),
                ('work_entry_type_id', 'any', [
                    ('count_as', '=', 'working_time'),
                    ('country_id.code', '=', 'BE')
                ])
            ])
            if not lines:
                continue
            worked_paid_hours = sum(l.number_of_hours for l in lines)
            if version.work_time_rate >= 1:
                workers_data[sex]['full'] += worked_paid_hours
                workers_data[sex]['fte'] += worked_paid_hours
            else:
                workers_data[sex]['part'] += worked_paid_hours
                workers_data[sex]['fte'] += worked_paid_hours
        report_data.update({
            '1011_male': round(workers_data['male']['full'], 2),
            '1011_female': round(workers_data['female']['full'], 2),
            '1011_total': round((workers_data['male']['full'] + workers_data['female']['full']), 2),
            '1012_male': round(workers_data['male']['part'], 2),
            '1012_female': round(workers_data['female']['part'], 2),
            '1012_total': round((workers_data['male']['part'] + workers_data['female']['part']), 2),
            '1013_male': round(workers_data['male']['fte'], 2),
            '1013_female': round(workers_data['female']['fte'], 2),
            '1013_total': round((workers_data['male']['fte'] + workers_data['female']['fte']), 2),
        })

        # SECTION 102 - 103: Staff Costs
        # Must be mentioned under heading 102 - "Expenses of personnel" charges which by reason of
        # their nature are entered under heading 62 of the minimum chart of accounts standardized,
        # provided that these loads concern workers covered by the social report (see above). Are
        # therefore included under the above heading, in so far as they concern the workers in
        # question:
        # - direct compensation and social benefits;
        # - employer's social contributions;
        # - employer premiums for extra-legal insurance;
        # - other personnel costs.
        workers_data = collections.defaultdict(lambda: collections.defaultdict(lambda: dict(full=0, part=0)))
        meal_voucher = dict(male=0, female=0, total=0)

        gross_codes = self.env['hr.payslip']._get_gross_wage_line_codes()
        line_values = payslips._get_line_values(
            [*gross_codes, 'CAR.PRIV', 'ONSSEMPLOYER', 'MEAL_V_EMP', 'PUB.TRANS', 'TRAIN', 'REP.FEES', 'IP.PART'], vals_list=['total', 'quantity'])
        for payslip in payslips:
            sex = payslip.version_id.sex
            if sex not in ['male', 'female']:
                raise UserError(self.env._('Please configure a sex (either male or female) for the following employee: %s', payslip.employee_id.name))
            contract_type = 'full' if version.work_time_rate >= 1 else 'part'
            gross = round(sum(line_values[code][payslip.id]['total'] for code in gross_codes), 2) - round(line_values['IP.PART'][payslip.id]['total'], 2)
            private_car = round(line_values['CAR.PRIV'][payslip.id]['total'], 2)
            public_transport = round(line_values['PUB.TRANS'][payslip.id]['total'], 2)
            onss_employer = round(line_values['ONSSEMPLOYER'][payslip.id]['total'], 2)
            reimbursed_expenses = round(line_values['REP.FEES'][payslip.id]['total'], 2)
            workers_data['total_gross'][sex][contract_type] += gross
            workers_data['private_car'][sex][contract_type] += private_car
            workers_data['public_transport'][sex][contract_type] += public_transport
            workers_data['onss_employer'][sex][contract_type] += onss_employer
            workers_data['reimbursed_expenses'][sex][contract_type] += reimbursed_expenses
            workers_data['total'][sex][contract_type] += gross + private_car + onss_employer + public_transport + reimbursed_expenses

            employer_amount = payslip.version_id.meal_voucher_paid_by_employer
            meal_voucher[sex] += round(employer_amount * line_values['MEAL_V_EMP'][payslip.id]['quantity'], 2)

        report_data['102'] = workers_data
        report_data['103'] = meal_voucher

        # SECTION 105-113, 120, 121, 130-134: At the end of the exercice
        workers_data = collections.defaultdict(lambda: dict(full=0, part=0, fte=0))

        end_contracts = self.env['hr.employee']._get_all_versions_with_contract_overlap_with_period(self.date_to, self.date_to)
        end_contracts = end_contracts.filtered(lambda c: c.l10n_be_worker_code_id.dmfa_code not in ['848', '849'] and any(s.state in ['validated', 'paid'] for s in c.employee_id.slip_ids))
        end_contracts_by_employees = collections.defaultdict(lambda: self.env['hr.version'])
        last_end_contracts = self.env['hr.version']
        for end_contract in end_contracts:
            end_contracts_by_employees[end_contract.employee_id] += end_contract
        for employee_contracts in end_contracts_by_employees.values():
            last_end_contracts += employee_contracts.sorted('date_version', reverse=True)[0]
        end_contracts = last_end_contracts

        replacement = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_replacement')
        defined_work = self.env.ref('l10n_be_hr_payroll.l10n_be_contract_type_clearly_defined_work')

        mapped_certificates = {
            ('male', 'graduate'): '1202',
            ('male', 'bachelor'): '1202',
            ('male', 'master'): '1203',
            ('male', 'doctor'): '1203',
            ('male', 'other'): '1201',
            ('male', False): '1201',
            ('male', 'civil_engineer'): '1203',
            ('female', 'graduate'): '1212',
            ('female', 'bachelor'): '1212',
            ('female', 'master'): '1213',
            ('female', 'doctor'): '1213',
            ('female', 'other'): '1211',
            ('female', False): '1211',
            ('female', 'civil_engineer'): '1213',
        }

        mapped_categories = {
            'oth': '134',
            'stu': '133',
        }

        for contract in end_contracts:
            contract_type = _get_contract_type_code(contract, replacement, defined_work)
            if not contract_type:
                _logger.info(self.env._("The contract %(contract_name)s for %(employee)s is not of one the following types: CDI, CDD. Replacement, For a clearly defined work", contract_name=contract.name, employee=contract.employee_id.name))
                continue
            dimona_category = contract.l10n_be_dimona_category
            if contract.l10n_be_worker_code_id.dmfa_code in ['848', '849']:
                # CIP Contracts are considered as trainees
                dimona_category = 'stu'
            if dimona_category not in mapped_categories:
                _logger.info(self.env._("The contract %(contract_name)s for %(employee)s is not of one the following types: CP200 Employees or Student", contract_name=contract.name, employee=contract.employee_id.name))
                continue

            sex = contract.employee_id.sex
            work_time_rate = version.work_time_rate

            contract_time = 'full' if work_time_rate >= 1 else 'part'

            workers_data['105'][contract_time] += 1
            workers_data['105']['fte'] += 1 * work_time_rate

            workers_data[contract_type][contract_time] += 1
            workers_data[contract_type]['fte'] += 1 * work_time_rate

            if (sex, contract.employee_id.certificate) not in mapped_certificates:
                raise UserError(self.env._("The employee %s doesn't have a specified certificate", contract.employee_id.name))
            sex_code = '120' if sex == 'male' else '121'
            workers_data[sex_code][contract_time] += 1
            workers_data[sex_code]['fte'] += 1 * work_time_rate
            sex_certificate_code = mapped_certificates[sex, contract.employee_id.certificate]
            workers_data[sex_certificate_code][contract_time] += 1
            workers_data[sex_certificate_code]['fte'] += 1 * work_time_rate

            category_code = mapped_categories[dimona_category]
            workers_data[category_code][contract_time] += 1
            workers_data[category_code]['fte'] += 1 * work_time_rate

        for code in [
                '105', '110', '111', '112', '113',
                '120', '1200', '1201', '1202', '1203',
                '121', '1210', '1211', '1212', '1213',
                '130', '132', '133', '134']:
            report_data[code] = workers_data[code]

        # SECTION 200: Staff Movements (Entries / Departure)
        workers_data = collections.defaultdict(lambda: dict(full=0, part=0, fte=0))

        in_employees = self.env['hr.employee']
        out_employees = self.env['hr.employee']
        for employee_payslips in mapped_payslips.values():
            if len(employee_payslips) > 1:
                # What matters is the occupation at the end of the month. Take the most recent contract
                payslip = employee_payslips.sorted(lambda p: p.version_id.date_start, reverse=True)[-1]
            else:
                payslip = employee_payslips
            employee = payslip.employee_id
            contract = payslip.version_id
            in_contract_type, out_contract_type = _get_in_out_contract_type_code(contract, replacement, defined_work)
            if not in_contract_type or not out_contract_type:
                _logger.info(self.env._("The contract %(contract_name)s for %(employee)s is not of one the following types: CDI, CDD. Replacement, For a clearly defined work", contract_name=contract.name, employee=contract.employee_id.name))
                continue

            work_time_rate = version.work_time_rate
            contract_time = 'full' if work_time_rate >= 1 else 'part'
            if employee not in in_employees and employee.contract_date_start and (self.date_from <= employee.contract_date_start <= self.date_to):
                in_employees |= employee

                workers_data['205'][contract_time] += 1
                workers_data['205']['fte'] += 1 * work_time_rate

                workers_data[in_contract_type][contract_time] += 1
                workers_data[in_contract_type]['fte'] += 1 * work_time_rate
            departure_date = employee.departure_date
            if departure_date and employee not in out_employees and (self.date_from <= departure_date <= self.date_to):
                out_employees |= employee

                workers_data['305'][contract_time] += 1
                workers_data['305']['fte'] += 1 * work_time_rate

                workers_data[out_contract_type][contract_time] += 1
                workers_data[out_contract_type]['fte'] += 1 * work_time_rate

                reason_code = employee.departure_reason_id.l10n_be_reason_code
                reason_code = str(reason_code if reason_code in [340, 341, 342, 343] else 343)
                workers_data[reason_code][contract_time] += 1
                workers_data[reason_code]['fte'] += 1 * work_time_rate

        for code in [
                '205', '210', '211', '212', '213',
                '305', '310', '311', '312', '313',
                '340', '341', '342', '343']:
            report_data[code] = workers_data[code]

        # SECTION 580: Trainings
        for code in ['5821', '5831', '5822', '5832', '5823', '5833', '5841', '5851', '5842', '5852', '5843',
            '5853', '58033', '58133', '5801', '5811', '5802', '5812', '58031', '58131', '58032', '58132',
            '5803', '5813']:
            report_data[code] = 0

        report_data['social_balance_sheet'] = report_data
        report_data['year'] = self.date_from.strftime('%Y')

        return report_data

    def print_report(self):
        report_data = self._get_report_data()
        filename = self.env._(
            'SocialBalance-%(date_from)s-%(date_to)s.pdf',
            date_from=format_date(self.env, self.date_from),
            date_to=format_date(self.env, self.date_to))
        export_social_balance_sheet_pdf, _ = self.env["ir.actions.report"].sudo()._render_qweb_pdf(
            self.env.ref('l10n_be_hr_payroll.action_report_social_balance').id,
            res_ids=self.ids, data={'sbs_data': report_data})

        self.social_balance_filename = filename
        self.social_balance_sheet = BinaryBytes(export_social_balance_sheet_pdf)
        self.state = 'done'
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Social Balance Sheet'),
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }

    def action_validate(self):
        self.ensure_one()
        if self.social_balance_sheet:
            self._post_process_generated_file(self.social_balance_sheet, self.social_balance_filename)
        return {'type': 'ir.actions.act_window_close'}

    # To be overwritten in documents_l10n_be_hr_payroll to create a document.document
    def _post_process_generated_file(self, data, filename):
        return
