from dateutil.relativedelta import relativedelta

from odoo import api, models, fields
from odoo.tools.translate import LazyTranslate


_lt = LazyTranslate(__name__)


class AccountReturn(models.Model):
    _inherit = 'account.return'

    l10n_uk_cis_status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('error', 'Error'),
        ],
        string="CIS Submission Status",
        help="Track the status of the CIS return submission for State Color."
    )

    def _compute_visible_states(self):
        super()._compute_visible_states()
        for record in self.filtered(lambda r: r.type_external_id == 'l10n_uk_reports_cis.uk_cis_tax_return_type'):
            new_visible_states = []
            for state_data in record.visible_states:
                if state_data['name'] == 'submitted':
                    if record.l10n_uk_cis_status == 'error':
                        state_data['alert_type'] = 'danger'
                    elif record.l10n_uk_cis_status == 'pending':
                        state_data['alert_type'] = 'warning'
                    elif record.l10n_uk_cis_status == 'accepted':
                        state_data['alert_type'] = 'success'
                new_visible_states.append(state_data)
            record.visible_states = new_visible_states

    def _get_vat_closing_entry_additional_domain(self):
        domain = super()._get_vat_closing_entry_additional_domain()
        if self.type_external_id == 'l10n_uk_reports.uk_tax_return_type':
            purchase_tax_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_deduction')._get_matching_tags()
            sales_tax_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_sale_expr_deduction')._get_matching_tags()
            tags = purchase_tax_tags + sales_tax_tags
            # EXTENDS account_reports
            domain += [
                ('tax_tag_ids', 'not in', tags.ids),  # Exclude CIS taxes lines from tax closing.
            ]
        return domain

    def _prepare_submission(self):
        # Extends account_reports
        if self.type_external_id == 'l10n_uk_reports_cis.uk_cis_tax_return_type':
            return self.env['cis.monthly.return.wizard']._open_submission_wizard(self)
        return super()._prepare_submission()

    def action_refresh_hmrc_request(self):
        transactions = self.env['l10n_uk.hmrc.transaction'].search([('state', '=', 'polling'), ('return_id', '=', self.id)])
        for transaction in transactions:
            transaction._send_poll_request()

    def action_reset_uk_cis_return(self):
        self.l10n_uk_cis_status = False
        self._reset_common()

    def _run_checks(self, check_codes_to_ignore):
        checks = super()._run_checks(check_codes_to_ignore)
        if self.type_external_id == 'l10n_uk_reports_cis.uk_cis_tax_return_type':
            checks += self._check_suite_common_vat_report(check_codes_to_ignore)
            checks += self._run_cis_checks(check_codes_to_ignore)
        return checks

    def _run_cis_checks(self, check_codes_to_ignore):
        self.ensure_one()
        checks = []
        if 'check_cis_company_data' not in check_codes_to_ignore:
            no_cis_fields = not self.env.company.l10n_uk_hmrc_unique_taxpayer_reference or not self.env.company.l10n_uk_hmrc_account_office_reference
            checks.append({
                'name': _lt("CIS data on the company"),
                'code': 'check_cis_company_data',
                'message': _lt("The company is missing some CIS data. Please fill in the missing fields in the company settings."),
                'action': self.env.company._get_records_action(),
                'result': 'anomaly' if no_cis_fields else 'reviewed',
            })

        if 'check_cis_unregistered_partners' not in check_codes_to_ignore:
            unregistered_partners = self.env['account.move']._read_group(
                domain=[
                    ('l10n_uk_cis_inactive_partner', '=', True),
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to),
                ],
                aggregates=['partner_id:recordset'],
            )[0][0]

            checks.append({
                'name': _lt("Subcontractor Verification"),
                'code': 'check_cis_unregistered_partners',
                'message': _lt("All subcontractors must be verified with HMRC, and have the correct CIS status applied"),
                'action': unregistered_partners._get_records_action() if unregistered_partners else None,
                'result': 'anomaly' if unregistered_partners else 'reviewed',
            })

        if 'check_cis_correct_deductions' not in check_codes_to_ignore:
            options = self._get_closing_report_options()
            checks.append({
                'name': _lt("Correct CIS Deductions"),
                'code': 'check_cis_correct_deductions',
                'message': _lt("Deductions must be correctly calculated and only applied to labour, excluding materials and VAT."),
                'action': {
                    'type': 'ir.actions.client',
                    'name': self.env._("CIS Report"),
                    'tag': 'account_report',
                    'context': {'report_id': self.type_id.report_id.id},
                    'params': {'options': options, 'ignore_session': True},
                },
            })

        if 'check_cis_materials_breakdown' not in check_codes_to_ignore:
            purchase_base_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_base')._get_matching_tags()
            cis_bill_amls = self.env['account.move.line'].search([
                ('move_type', 'in', self.env['account.move'].get_purchase_types()),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('company_id', 'in', self.company_ids.ids),
                ('parent_state', '=', 'posted'),
                ('tax_tag_ids', 'in', purchase_base_tags.ids),
            ])
            action = {
                'type': 'ir.actions.act_window',
                'name': self.env._("CIS Bill Items"),
                'view_mode': 'list',
                'res_model': 'account.move.line',
                'domain': [('id', 'in', cis_bill_amls.ids)],
                'views': [[False, 'list']],
            }
            checks.append({
                'name': _lt("Materials Breakdown"),
                'code': 'check_cis_materials_breakdown',
                'message': _lt("Labour and materials must be clearly separated, with materials supported by evidence."),
                'action': action,
            })

        if 'check_cis_compliance_declaration' not in check_codes_to_ignore:
            purchase_deduction_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_deduction')._get_matching_tags()
            sales_deduction_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_sale_expr_deduction')._get_matching_tags()
            cis_deduction_tags = purchase_deduction_tags + sales_deduction_tags
            employee_partners = self.env['account.move']._read_group(
                domain=[
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to),
                    ('company_id', 'in', self.company_ids.ids),
                    ('state', '=', 'posted'),
                    ('partner_id.employee', '=', True),
                    ('line_ids.tax_tag_ids', 'in', cis_deduction_tags.ids),
                ],
                aggregates=['partner_id:recordset'],
            )[0][0]
            checks.append({
                'name': _lt("Compliance Declaration"),
                'code': 'check_cis_compliance_declaration',
                'message': _lt("Confirm all subcontractors are correctly treated and none should be employees."),
                'action': employee_partners._get_records_action() if employee_partners else None,
                'result': 'anomaly' if employee_partners else 'reviewed',
            })

        return checks


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    @api.depends('report_id')
    def _compute_report_return_type(self):
        # CIS return type should not create a closing entry
        super()._compute_report_return_type()
        cis_return_type = self.env.ref('l10n_uk_reports_cis.uk_cis_tax_return_type')
        self.filtered(lambda r: r.id == cis_return_type.id).is_tax_return_type = False

    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        rslt = super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)
        if country_code == 'GB':
            # Auto generate CIS returns for every period that has CIS move lines
            cis_return_type = self.env.ref('l10n_uk_reports_cis.uk_cis_tax_return_type')
            cis_tax_tags = (
                self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_deduction')._get_matching_tags()
                + self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_sale_expr_deduction')._get_matching_tags()
            )
            company_ids = self.env['account.return'].sudo()._get_company_ids(main_company, tax_unit, cis_return_type.report_id)

            today = fields.Date.context_today(self)
            months_offset = cis_return_type._get_periodicity_months_delay(main_company)
            periods = [today + relativedelta(months=months_offset * i) for i in range(-3, 2)]

            periods_has_move_lines_map = {
                period_bounds: bool(self.env['account.move.line'].search_count([
                    ('tax_tag_ids', 'in', cis_tax_tags.ids),
                    *self.env['account.move.line']._check_company_domain(company_ids.ids),
                    ('date', '>=', period_bounds[0]),
                    ('date', '<=', period_bounds[1]),
                ], limit=1))
                for period_bounds in (
                    cis_return_type._get_period_boundaries(main_company, period)
                    for period in periods
                )
            }

            for (start, end), has_lines in periods_has_move_lines_map.items():
                if has_lines:
                    cis_return_type._try_create_return_for_period(start, main_company, tax_unit=tax_unit)

        return rslt
