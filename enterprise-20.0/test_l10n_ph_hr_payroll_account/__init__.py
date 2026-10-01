# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.fields import Datetime
from dateutil.rrule import rrule, MONTHLY


def _generate_payslips(env):
    # Do this only when demo data is activated
    if env.ref('base.demo_company_ph', raise_if_not_found=False):
        anna = env.ref('l10n_ph_hr_payroll.hr_employee_ph_anna', raise_if_not_found=False)
        juan = env.ref('l10n_ph_hr_payroll.hr_employee_ph_juan', raise_if_not_found=False)
        mary = env.ref('l10n_ph_hr_payroll.hr_employee_ph_mary', raise_if_not_found=False)
        jose = env.ref('l10n_ph_hr_payroll.hr_employee_ph_jose', raise_if_not_found=False)
        if not any([anna, juan, mary, jose]):
            return

        # Create demo data from jan last year (or employee start date) to this month
        employees = anna | juan | mary | jose
        _prepare_demo_batches(env, employees, Datetime.now() + relativedelta(years=-1, month=6))


def _prepare_demo_batches(env, employees, start_month):
    payruns_data = []
    payrun_date = start_month + relativedelta(day=1)
    end_date = date.today()
    for structure_id, employees in employees.grouped('structure_id').items():
        for dt in rrule(MONTHLY, dtstart=payrun_date, until=end_date):
            concerned_versions = employees.version_id.filtered(lambda v: v._is_in_contract(dt.date()))
            # Payruns are semi-monthly
            payruns_data.append({
                'date_start': dt,
                'date_end': dt + relativedelta(day=15),
                'structure_id': structure_id.id,
                'version_ids': concerned_versions.ids,
            })
            payruns_data.append({
                'date_start': dt + relativedelta(day=16),
                'date_end': dt + relativedelta(day=31),
                'structure_id': structure_id.id,
                'version_ids': concerned_versions.ids,
            })

    payruns = env['hr.payslip.run'].with_company(env.ref('base.demo_company_ph')).create(payruns_data)
    for i, payrun in enumerate(payruns):
        payrun._generate_payslips()
        if i < (len(payruns) - 1) or end_date != date.today():
            # We process all payruns one at a time, because otherwise rules depending on the previous payslips being validated wouldn't work.
            payrun.action_validate()
            payrun.action_paid()

    # To ease testing of yearly reports, we can pre-generate the monthly 1601-C for the first year.
    # As the 1604-C expects both 1601-C and 2316 to exist to avoid warnings, we'll also create a 2316.
    declaration_data = []
    for dt in rrule(MONTHLY, dtstart=payrun_date, until=payrun_date + relativedelta(month=12, day=31)):
        declaration_data.append({
            'period_start_date': dt,
            'period_end_date': dt + relativedelta(day=31),
            'state': 'done',
        })
    declarations = env['l10n_ph_hr_payroll.form_1601c'].with_company(env.ref('base.demo_company_ph')).create(declaration_data)
    for declaration in declarations:
        declaration.action_generate_declarations()
        declaration.action_process_declaration()
    # Add the one yearly 2316 too
    declaration = env['l10n_ph_hr_payroll.form_2316'].with_company(env.ref('base.demo_company_ph')).create({
        'period_start_date': payrun_date,
        'period_end_date': payrun_date + relativedelta(month=12, day=31),
        'state': 'done',
    })
    declaration.action_generate_declarations()
