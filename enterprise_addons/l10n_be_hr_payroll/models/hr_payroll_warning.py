from dateutil.relativedelta import relativedelta

from odoo import models
from odoo import fields
from odoo.fields import Domain


class HrPayrollWarning(models.Model):
    _inherit = 'hr.payroll.warning'
    l10n_be_joint_committee_ids = fields.Many2many(
            comodel_name='l10n.be.joint.committee',
            string="Joint Committees",
            help="List all joint committees where the warning should be applied",
            context={'active_test': False},
        )
    l10n_be_excluded_joint_committee_ids = fields.Many2many(
        comodel_name='l10n.be.joint.committee',
        relation='warning_joint_committee_rel',
        string="Excluded Joint Committees",
        help="List all joint committees where the warning should not be applied",
        context={'active_test': False},
    )

    def _get_allowed_models(self):
        res = super()._get_allowed_models()
        country_code = self.country_id.code or self.env.company.country_id.code
        if country_code == 'BE':
            res += ['l10n_be.dmfa']
        return res

    def _l10n_be_is_period_undeclared(self, company, date_start, date_end):
        """Does this period hold amounts that no filed 274.XX declares?

        This replaces a "period to report" flag stored on the payslip: whether something is left
        to declare is asked of payroll and of the declarations, so it cannot go stale and cannot
        hide a payslip from another declaration stream.
        """
        covered = self.env['l10n_be.274_xx'].sudo().search_count([
            ('company_id', '=', company.root_id.id),
            ('state', '=', 'done'),
            ('date_start', '<=', date_start),
            ('date_end', '>=', date_end),
        ], limit=1)
        return not covered and self._check_payslips_for_report(company, date_start, date_end)

    def _check_payslips_for_report(self, company, date_start, date_end, domain=None):
        payslips = self.env['hr.payslip']
        payslip_domain = Domain([
            ('state', 'in', ['paid', 'validated']),
            ('company_id', '=', company.id),
        ]) & payslips._l10n_be_get_fiscal_period_domain(date_start, date_end)
        # Warn only when the period really holds amounts to declare: a payslip may be attached to
        # it by its fiscal date while every one of its lines follows the pay period, or the other
        # way round.
        payslip_domain &= Domain('line_ids', 'any', payslips._l10n_be_get_fiscal_line_domain(date_start, date_end))
        if domain:
            payslip_domain &= Domain(domain)
        return bool(self.env['hr.payslip'].search_count(payslip_domain, limit=1))

    def action_l10n_be_report_warning(self):
        report_ids = self.env.context.get('report_ids', False)
        model_name = self.env.context.get('model_name', False)
        has_certificate = self.env.context.get('has_certificate', False)
        vals = self.env.context.get('vals', {})
        if not model_name:
            return
        report_name = model_name.split('.')[1]
        # if the report is created but the warning is not reloaded
        if not report_ids:
            domain = [(key, '=', value) for key, value in vals.items()]
            existing_reports = self.env[model_name].search(domain)
            report_ids = existing_reports.ids
        if not report_ids:
            new_report = self.env[model_name].create(vals)
            action_name = '27x' if report_name in ('273_xx', '274_xx') else report_name
            return {
                'type': 'ir.actions.client',
                'tag': f'l10n_be_hr_payroll.report_{action_name}_warning_action',
                'target': 'new',
                'params': {
                    'report_id': new_report.id,
                    'model_name': model_name,
                    'has_certificate': has_certificate,
                },
            }
        else:
            if len(report_ids) == 1:
                return {
                    'name': self.env._("%s report", report_name),
                    'res_model': model_name,
                    'type': 'ir.actions.act_window',
                    'res_id': report_ids[0],
                    'views': [(False, 'form')],
                }
            else:
                return {
                    'name': self.env._("%s reports", report_name),
                    'res_model': model_name,
                    'type': 'ir.actions.act_window',
                    'domain': [('id', 'in', report_ids)],
                    'views': [(False, 'list'), (False, 'form')],
                }

    def _get_l10n_be_profit_sharing_bonus_warning_payslips(self, extra_domain=None):
        companies = self.env.companies.filtered(lambda c: c.country_id.code == 'BE')
        if not companies:
            return self.env['hr.payslip']
        return self.env['hr.payslip'].search([
            ('company_id', 'in', companies.ids),
            ('struct_id.code', '=', 'BEPROFITSHARING'),
        ] + (extra_domain or []))

    def action_cancel_draft_payslip_not_eligible_to_profit_sharing(self):
        wrong_employer_category_extra_domain = [
            ("payroll_config_id.l10n_be_employer_category_id.dmfa_code", "in", ("037", "039", "212")),
            ("state", "=", "draft"),
        ]
        payslips = self._get_l10n_be_profit_sharing_bonus_warning_payslips(wrong_employer_category_extra_domain)
        payslips.action_payslip_cancel()
        payslips = self._get_l10n_be_profit_sharing_bonus_warning_payslips()
        return payslips._get_records_action(name=self.env._('Profit Sharing Bonus Payslips (Invalid Employer Category)'))

    def action_cancel_draft_payslip_employee_less_than_one_year_service_profit_sharing(self):
        less_than_one_year_extra_domain = [
            ("state", "=", "draft"),
            ("employee_id.first_contract_date", "!=", False),
        ]
        payslips = self._get_l10n_be_profit_sharing_bonus_warning_payslips(less_than_one_year_extra_domain)
        payslips = payslips.filtered(lambda p: p.employee_id.first_contract_date > p.date_from + relativedelta(years=-1))
        payslips.action_payslip_cancel()
        payslips = self._get_l10n_be_profit_sharing_bonus_warning_payslips([
            ("employee_id.first_contract_date", "!=", False),
        ]).filtered(lambda p: p.employee_id.first_contract_date > p.date_from + relativedelta(years=-1))
        return payslips._get_records_action(name=self.env._('Profit Sharing Bonus Payslips (Less than 1 Year of Service)'))

    def _get_payroll_translation(self, text, **kwargs):
        # Please order alphabetically to easily spot duplicates
        if text == "%(days)s days of Paid time off remaining.\nThe employee was sick in december and couldn't take all paid time off. You can decide to postpone them for next year.":
            return self.env._("%(days)s days of Paid time off remaining.\nThe employee was sick in december and couldn't take all paid time off. You can decide to postpone them for next year.", **kwargs)
        if text == "%(days)s days of Postponed off remaining.\nThe employee was sick during all this year and couldn't take the paid time off postponed from the previous year. You can decide to postpone them again to next year.":
            return self.env._("%(days)s days of Postponed off remaining.\nThe employee was sick during all this year and couldn't take the paid time off postponed from the previous year. You can decide to postpone them again to next year.", **kwargs)
        if text == "Adjust Wage":
            return self.env._("Adjust Wage")
        if text == "Cannot encode additional hours during regular working time.":
            return self.env._("Cannot encode additional hours during regular working time.")
        if text == "Continue":
            return self.env._("Continue")
        if text == "Correct":
            return self.env._("Correct")
        if text == "Daily hours exceed 9h limit convert excess to Extra-hours.":
            return self.env._("Daily hours exceed 9h limit convert excess to Extra-hours.")
        if text == "December departure payslip has an unrecovered net amount of %(amount)s.":
            return self.env._("December departure payslip has an unrecovered net amount of %(amount)s.", **kwargs)
        if text == "December payslip has an unrecovered net amount of %(amount)s.":
            return self.env._("December payslip has an unrecovered net amount of %(amount)s.", **kwargs)
        if text == "Departure payslip has an unrecovered net amount of %(amount)s.":
            return self.env._("Departure payslip has an unrecovered net amount of %(amount)s.", **kwargs)
        if text == "DMFA employees missing DIMONA %(names)s":
            return self.env._("DMFA employees missing DIMONA %(names)s", **kwargs)
        if text == "DMFA Submission %(year)s Q%(quarter)s":
            return self.env._("DMFA Submission %(year)s Q%(quarter)s", **kwargs)
        if text == "Draft payslips excluded.":
            return self.env._("Draft payslips excluded.")
        if text == "Edit":
            return self.env._("Edit")
        if text == "Employee's wage is below the minimum wage for their salary scale. Minimum wage is %(min_wage)s%(currency)s":
            return self.env._("Employee's wage is below the minimum wage for their salary scale. Minimum wage is %(min_wage)s%(currency)s", **kwargs)
        if text == "Employees exceeding quarterly occupation days %(names)s":
            return self.env._("Employees exceeding quarterly occupation days %(names)s", **kwargs)
        if text == "Employees missing DMFA worker code %(names)s":
            return self.env._("Employees missing DMFA worker code %(names)s", **kwargs)
        if text == "Employees require paid time off allocation for %(year)s":
            return self.env._("Employees require paid time off allocation for %(year)s", **kwargs)
        if text == "Employees with work address missing ONSS code %(names)s":
            return self.env._("Employees with work address missing ONSS code %(names)s", **kwargs)
        if text == "Employer category required to import ONSS rates.":
            return self.env._("Employer category required to import ONSS rates.")
        if text == "Invalid license plates %(names)s":
            return self.env._("Invalid license plates %(names)s", **kwargs)
        if text == "Mark as done":
            return self.env._("Mark as done")
        if text == "Max 12 additional hours/month pay excess at +50% or +100%.":
            return self.env._("Max 12 additional hours/month pay excess at +50% or +100%.")
        if text == "Meal vouchers exceed annual limit (%(max_count)s).":
            return self.env._("Meal vouchers exceed annual limit (%(max_count)s).", **kwargs)
        if text == "Missing employer class for company: %(name)s.":
            return self.env._("Missing employer class for company: %(name)s.", **kwargs)
        if text == "Missing NISS for employees %(names)s":
            return self.env._("Missing NISS for employees %(names)s", **kwargs)
        if text == "Missing ONSS company ID for company: %(name)s.":
            return self.env._("Missing ONSS company ID for company: %(name)s.", **kwargs)
        if text == "Mobility Budget amount exceeds 20%% of the yearly wage (%(amount).2f €).":
            return self.env._("Mobility Budget amount exceeds 20%% of the yearly wage (%(amount).2f €).", **kwargs)
        if text == "Mobility Budget amount exceeds the maximum allowed value (%(amount).2f €).":
            return self.env._("Mobility Budget amount exceeds the maximum allowed value (%(amount).2f €).", **kwargs)
        if text == "Mobility Budget amount is below the minimum allowed value (%(amount).2f €).":
            return self.env._("Mobility Budget amount is below the minimum allowed value (%(amount).2f €).", **kwargs)
        if text == "Mobility expense payout (%(mobility_to_pay)s €) requires an active mobility budget.":
            return self.env._("Mobility expense payout (%(mobility_to_pay)s €) requires an active mobility budget.", **kwargs)
        if text == "More than 2 days of sick time off without certificate have been taken this year (%(days)s days)":
            return self.env._("More than 2 days of sick time off without certificate have been taken this year (%(days)s days)", **kwargs)
        if text == "Occupation days mismatch working schedule %(names)s":
            return self.env._("Occupation days mismatch working schedule %(names)s", **kwargs)
        if text == "Only one day of sick time off can be flagged without certificate":
            return self.env._("Only one day of sick time off can be flagged without certificate")
        if text == "Salary below %(limit)s%(currency)s threshold transport benefit required.":
            return self.env._("Salary below %(limit)s%(currency)s threshold transport benefit required.", **kwargs)
        if text == "See addresses":
            return self.env._("See addresses")
        if text == "See company settings":
            return self.env._("See company settings")
        if text == "See employees":
            return self.env._("See employees")
        if text == "See payslips":
            return self.env._("See payslips")
        if text == "See time types":
            return self.env._("See time types")
        if text == "See vehicles":
            return self.env._("See vehicles")
        if text == "See versions":
            return self.env._("See versions")
        if text == "Set Employer Category":
            return self.env._("Set Employer Category")
        if text == "Start":
            return self.env._("Start")
        if text == "Sunday additional hours must be paid.":
            return self.env._("Sunday additional hours must be paid.")
        if text == "The employee is under the legal minimum working age (18 years old)":
            return self.env._("The employee is under the legal minimum working age (18 years old)")
        if text == "The student is under the legal minimum working age (15 years old)":
            return self.env._("The student is under the legal minimum working age (15 years old)")
        if text == "Tax Forms 281, %(year)s":
            return self.env._("Tax Forms 281, %(year)s", **kwargs)
        if text == "Termination payslips missing notice period dates %(names)s":
            return self.env._("Termination payslips missing notice period dates %(names)s", **kwargs)
        if text == "The intellectual property limit of %(limit)s is reached: the exceeding part is paid as a regular remuneration":
            return self.env._("The intellectual property limit of %(limit)s is reached: the exceeding part is paid as a regular remuneration", **kwargs)
        if text == "The remaining mobility budget can't be negative (%(mobility_remaining)s €). Adjust Pillar 2 or Pillar 3 amounts to resolve the deficit.":
            return self.env._("The remaining mobility budget can't be negative (%(mobility_remaining)s €). Adjust Pillar 2 or Pillar 3 amounts to resolve the deficit.", **kwargs)
        if text == "The total number of meal vouchers for this year exceeds %(max_count)s":
            return self.env._("The total number of meal vouchers for this year exceeds %(max_count)s", **kwargs)
        if text == "There are %(count)s public holiday(s) in the 30/14th days following the end of the contract, it should be paid if the employee didn't find a new job.":
            return self.env._("There are %(count)s public holiday(s) in the 30/14th days following the end of the contract, it should be paid if the employee didn't find a new job.", **kwargs)
        if text == "Time types missing DMFA code %(names)s":
            return self.env._("Time types missing DMFA code %(names)s", **kwargs)
        if text == "This employee is not eligible to be paid for Work accident or Work illness (009.00). 110.00 should be used instead.":
            return self.env._("This employee is not eligible to be paid for Work accident or Work illness (009.00). 110.00 should be used instead.")
        if text == "This time off will be split into:\n%(lines)s":
            return self.env._("This time off will be split into:\n%(lines)s", **kwargs)
        if text == "This time off will be entirely replaced with %(code)s - %(name)s":
            return self.env._("This time off will be entirely replaced with %(code)s - %(name)s", **kwargs)
        if text == "Weekly hours exceed schedule limit convert excess to Extra-hours.":
            return self.env._("Weekly hours exceed schedule limit convert excess to Extra-hours.")
        if text == "Time Off with Exceeded Duration":
            return self.env._("Time Off with Exceeded Duration")
        if text == "This sub-type can only be used until December 31 of the year the employee turns 18.":
            return self.env._("This sub-type can only be used until December 31 of the year the employee turns 18.")
        if text == "Too many Additional Hours per day.\nThe number of Additional Hours and working hours can not exceed 9h per day, transform the exceeding hours into Extra-hours":
            return self.env._("Too many Additional Hours per day.\nThe number of Additional Hours and working hours can not exceed 9h per day, transform the exceeding hours into Extra-hours")
        if text == "Too many Additional Hours per month.\nThe number of Additional Hours can not exceed 12h per month, exceeding hours should be paid +50% or +100%":
            return self.env._("Too many Additional Hours per month.\nThe number of Additional Hours can not exceed 12h per month, exceeding hours should be paid +50% or +100%")
        if text == "Too many Additional Hours per week.\nThe number of Additional Hours and working hours can not exceed the reference working schedule, transform the exceeding hours into Extra-hours":
            return self.env._("Too many Additional Hours per week.\nThe number of Additional Hours and working hours can not exceed the reference working schedule, transform the exceeding hours into Extra-hours")
        if text == "Update Sub-type":
            return self.env._("Update Sub-type")
        if text == "Withholding taxes: %(date)s %(year)s":
            return self.env._("Withholding taxes: %(date)s %(year)s", **kwargs)
        if text == "Withholding taxes on Intellectual Property & Employee Participation: %(date)s %(year)s":
            return self.env._("Withholding taxes on Intellectual Property & Employee Participation: %(date)s %(year)s", **kwargs)
        if text == "Working schedule cannot exceed 38h/week.":
            return self.env._("Working schedule cannot exceed 38h/week.")
        if text == "Wrong work code (worker is too young)":
            return self.env._("Wrong work code (worker is too young)")
        if text == "- %(code)s - %(name)s: %(nbr_days)s days":
            return self.env._("- %(code)s - %(name)s: %(nbr_days)s days", **kwargs)
        return super()._get_payroll_translation(text, **kwargs)
