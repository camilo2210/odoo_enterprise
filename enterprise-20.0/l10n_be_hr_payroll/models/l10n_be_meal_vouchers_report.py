import calendar
import csv
import io
from datetime import date
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.binary import BinaryBytes
from odoo.tools.sql import drop_view_if_exists, SQL


class L10nBeMealVouchersReport(models.Model):
    _name = 'l10n_be.meal.vouchers.report'
    _description = 'Belgian Meal Vouchers Configuration'
    _rec_name = 'name'
    _order = 'year, month, id'

    def _get_default_company_id(self):
        return self.env.company

    company_id = fields.Many2one('res.company',
                                 required=True,
                                 default=_get_default_company_id,
                                 )
    branch_ids = fields.One2many('res.company', compute='_compute_branch_ids', compute_sudo=True)
    year = fields.Selection(
        selection='_get_range_of_years',
        default=lambda self: fields.Date.context_today(self).year,
        string='Period',
        required=True,
    )
    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December')],
        required=True, string='Month')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ready', 'Ready'),
        ('done', 'Done'),
        ('canceled', 'Canceled'),
    ], string='Status', default='draft', required=True)
    ref = fields.Char(string='Ref')
    employee_count = fields.Integer(string='Employees', compute='_compute_line_item_counts_and_total_value')
    voucher_count = fields.Integer(string='Meal Vouchers', compute='_compute_line_item_counts_and_total_value')
    total_value = fields.Integer(string='Value', compute='_compute_line_item_counts_and_total_value')
    currency_id = fields.Many2one(related='company_id.currency_id')
    export_filename_csv = fields.Char()
    export_filename_xlsx = fields.Char()
    export_file_csv = fields.Binary(string='Exported File CSV')
    export_file_xlsx = fields.Binary(string='Exported File XLSX')
    meal_vouchers_line_ids = fields.One2many(
        'l10n_be.meal.vouchers.line', compute='_compute_meal_vouchers_line_ids',
        string='Details')
    payslips_count = fields.Integer(compute='_compute_payslips_count')
    name = fields.Char(compute="_compute_name", store=True)

    _company_period_uniq = models.Constraint(
        'UNIQUE(company_id, year, month)',
        'Should be unique.',
    )

    def _get_range_of_years(self):
        current_year = fields.Date.today().year
        return [(year, year) for year in range(current_year, current_year - 6, -1)]

    @api.model
    def _get_default_period_values(self):
        today = fields.Date.context_today(self)
        latest_report = self.env['l10n_be.meal.vouchers.report'].search(
            [('company_id', '=', self.env.company.id)],
            order='year desc, month desc, id desc',
            limit=1,
        )
        if not latest_report:
            return str(today.year), str(today.month)
        year = int(latest_report.year)
        month = int(latest_report.month)
        if month == 12:
            return str(year + 1), '1'
        return str(year), str(month + 1)

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)
        if ('month' in fields and 'month' not in values) or ('year' in fields and 'year' not in values):
            default_year, default_month = self._get_default_period_values()
            if 'year' in fields and 'year' not in values:
                values['year'] = default_year
            if 'month' in fields and 'month' not in values:
                values['month'] = default_month
        return values

    @api.model
    def action_list_view(self):
        if self.env.company.country_id.code != "BE":
            raise UserError(
                self.env._("This feature seems to be as exclusive as Belgian chocolates. "
                "You must be logged in to a Belgian company to use it."),
            )

        return self.env["ir.actions.act_window"]._for_xml_id("l10n_be_hr_payroll.l10n_be_meal_vouchers_action")

    @api.depends('month', 'year')
    def _compute_name(self):
        month_labels = dict(self._fields['month']._description_selection(self.env))
        for report in self:
            if report.month and report.year:
                month_label = month_labels.get(report.month, report.month)
                report.name = self.env._(
                    'Meal vouchers report %(month)s, %(year)s',
                    month=month_label,
                    year=report.year,
                )
            elif report.month:
                month_label = month_labels.get(report.month, report.month)
                report.name = self.env._('Meal vouchers report %s') % month_label
            elif report.year:
                report.name = self.env._('Meal vouchers report %s') % report.year
            else:
                report.name = self.env._('Meal vouchers report')

    @api.depends('company_id')
    def _compute_branch_ids(self):
        report_companies = self.mapped('company_id')
        branches_by_root = self.env['res.company'].search([
            ('id', 'child_of', report_companies.ids),
        ]).grouped('root_id')

        for report in self:
            report.branch_ids = branches_by_root.get(report.company_id, report.company_id)

    @api.depends('year', 'month', 'company_id', 'state')
    def _compute_meal_vouchers_line_ids(self):
        for report in self:
            if not report.year or not report.month or not report.company_id:
                report.meal_vouchers_line_ids = False
                continue
            if report.state == 'done':
                report.meal_vouchers_line_ids = self.env['l10n_be.meal.vouchers.line'].search([
                    ('report_id', '=', report.id),
                ])
            else:
                company_ids = report.branch_ids.ids
                if self.env.company.parent_id:
                    company_ids = self.env.company.id

                report.meal_vouchers_line_ids = self.env['l10n_be.meal.vouchers.line'].sudo().search([
                    ('report_id', '=', False),
                    ('company_id', 'in', company_ids),
                    ('year', '=', report.year),
                    ('month', '=', report.month),
                ])

    @api.depends('meal_vouchers_line_ids')
    def _compute_line_item_counts_and_total_value(self):
        for report in self:
            lines = report.meal_vouchers_line_ids
            report.employee_count = len(lines.mapped('employee_id'))
            report.voucher_count = sum(lines.mapped('total'))
            report.total_value = sum(lines.mapped('total_value'))

    @api.depends('year', 'month', 'company_id', 'state')
    def _compute_payslips_count(self):
        for report in self:
            report.payslips_count = len(report._get_related_payslips())

    def write(self, vals):
        if 'month' in vals or 'year' in vals:
            for record in self:
                if (vals.get('month', record.month) != record.month or
                        vals.get('year', record.year) != record.year):
                    vals.update({
                        'export_file_csv': False,
                        'export_filename_csv': False,
                        'export_file_xlsx': False,
                        'export_filename_xlsx': False,
                        'state': 'draft',
                    })
                    break
        return super().write(vals)

    def action_open_payslips(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_view_hr_payslip_month_form')
        action['domain'] = [('id', 'in', self._get_related_payslips().ids)]
        return action

    def action_download(self):
        field = self.env.context.get('field')
        filename = self.env.context.get('filename')
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self._name}/{self.id}/{field}/{self[filename]}?download=true',
            'target': 'self',
        }

    def _get_related_payslips(self):
        """
        Return the payslips of the current month + correction payslips of the previous months
        We don't include reverted payslips
        """
        self.ensure_one()
        if not self.year or not self.month:
            return self.env['hr.payslip']
        if self.state == 'done':
            return self.env['hr.payslip'].search([
                ('l10n_be_meal_vouchers_report_id', '=', self.id),
                ('is_refund_payslip', '=', False),
            ])
        current_month_start = date(int(self.year), int(self.month), 1)
        last_day = calendar.monthrange(int(self.year), int(self.month))[1]
        current_month_end = date(int(self.year), int(self.month), last_day)
        # Current month payslips
        current_month_payslips = self.env['hr.payslip'].search(_get_payslips_domain(
            branch_ids=self.branch_ids.ids,
            date_from=current_month_start,
            date_to=current_month_end,
        ))
        # Correction payslips from previous months
        previous_month_correction_payslips = self.env['hr.payslip'].search(_get_payslips_domain(
            branch_ids=self.branch_ids.ids,
            date_from=None,
            prev_date_from=current_month_start,
            report_id=False
        ))
        line_values = previous_month_correction_payslips._get_line_values(['MEAL_V_EMP'])
        previous_month_correction_payslips = previous_month_correction_payslips.filtered(
            lambda p: line_values['MEAL_V_EMP'][p.id]['total'] < 0)
        return current_month_payslips | previous_month_correction_payslips

    def action_generate_meal_vouchers_report(self):
        self.ensure_one()

        headers = ['Name', 'NISS', 'Value', 'Quantity', 'Total']
        rows = []
        for line in self.meal_vouchers_line_ids.sorted('employee_id'):
            rows.append((
                line.employee_id.name or '',
                line.employee_id.niss or '',
                (line.total_value / line.total if line.total else 0),
                line.total,
                line.total_value,
            ))

        filename = f"{self.year}_{str(self.month).zfill(2)}_MealVoucher"
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        file_content_csv = output.getvalue().encode('utf-8')
        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Meal Vouchers')
        header_format = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#E0E0E0'})
        money_format = workbook.add_format({'num_format': '#,##0.00'})

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        for row_index, row in enumerate(rows, start=1):
            worksheet.write(row_index, 0, row[0])
            worksheet.write(row_index, 1, row[1])
            worksheet.write_number(row_index, 2, row[2] or 0, money_format)
            worksheet.write_number(row_index, 3, row[3] or 0)
            worksheet.write_number(row_index, 4, row[4] or 0, money_format)

        worksheet.set_column(0, 0, 30)
        worksheet.set_column(1, 1, 18)
        worksheet.set_column(2, 4, 12)
        workbook.close()
        file_content_xlsx = output.getvalue()

        self.write({
            'export_filename_csv': filename + '.csv',
            'export_file_csv': BinaryBytes(file_content_csv),
            'export_filename_xlsx': filename + '.xlsx',
            'export_file_xlsx': BinaryBytes(file_content_xlsx),
            'state': 'ready',
        })

    @api.model
    def _action_generate_current_month_report(self):
        today = fields.Date.context_today(self)
        month = str(today.month)
        year = str(today.year)

        report = self.search([
            ('company_id', '=', self.company_id.id),
            ('month', '=', month),
            ('year', '=', year),
        ], limit=1)
        if not report:
            report = self.create({
                'company_id': self.env.company.id,
                'month': month,
                'year': year,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Meal Vouchers'),
            'res_model': 'l10n_be.meal.vouchers.report',
            'view_mode': 'form',
            'res_id': report.id,
            'target': 'current',
        }

    def _link_payslips_to_report(self):
        self.ensure_one()
        if not self.year or not self.month:
            return
        last_day = calendar.monthrange(int(self.year), int(self.month))[1]
        period_end = date(int(self.year), int(self.month), last_day)
        payslips = self.env['hr.payslip'].search(_get_payslips_domain(
            branch_ids=self.branch_ids.ids,
            date_from=None,
            date_to=period_end,
            report_id=False,
        ))
        payslips.write({'l10n_be_meal_vouchers_report_id': self.id})

    def _unlink_payslips_from_report(self):
        self.ensure_one()
        payslips = self.env['hr.payslip'].search([
            ('l10n_be_meal_vouchers_report_id', '=', self.id),
        ])
        payslips.write({'l10n_be_meal_vouchers_report_id': False})

    def action_set_state(self, target_state=None):
        target_state = target_state or self.env.context.get('target_state')
        allowed_states = dict(self._fields['state']._description_selection(self.env))
        if target_state not in allowed_states:
            raise UserError(self.env._(
                'Invalid target state: %s',
                target_state,
            ))
        for report in self:
            if target_state == 'done':
                report._link_payslips_to_report()
            elif target_state in ('canceled', 'draft') and report.state == 'done':
                report._unlink_payslips_from_report()
        self.write({'state': target_state})

    @api.ondelete(at_uninstall=False)
    def _unlink_if_cancelled(self):
        non_cancelled_reports = self.filtered(lambda report: report.state not in ('canceled'))
        if non_cancelled_reports:
            raise UserError(self.env._(
                'You can only delete meal voucher reports in the "Cancelled" state.',
            ))


class L10nBeMealVouchersLine(models.Model):
    _name = 'l10n_be.meal.vouchers.line'
    _description = 'Belgian Meal Vouchers Line'
    _auto = False

    report_id = fields.Many2one('l10n_be.meal.vouchers.report', string='Meal Voucher Report', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    year = fields.Char(string='Year', readonly=True)
    month = fields.Char(string='Month', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', readonly=True)
    entitlement = fields.Integer(string='This month', readonly=True)
    postponed = fields.Integer(string='Postponed', readonly=True)
    total = fields.Integer(string="Total", readonly=True)
    total_value = fields.Monetary(string='TotalValue', readonly=True)
    value = fields.Monetary(string='Value', compute='_compute_value')
    currency_id = fields.Many2one(related='employee_id.currency_id', string='Currency', readonly=True)

    @api.depends('total_value', 'total')
    def _compute_value(self):
        for line in self:
            line.value = line.total_value / line.total if line.total else 0

    def init(self):
        drop_view_if_exists(self.env.cr, self._table)
        statement = SQL("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ROW_NUMBER() OVER () AS id,
                    sub.report_id,
                    sub.company_id,
                    sub.year,
                    sub.month,
                    sub.employee_id,
                    SUM(sub.entitlement)::INTEGER AS entitlement,
                    ABS(SUM(sub.postponed))::INTEGER AS postponed,
                    (SUM(sub.entitlement) - SUM(sub.postponed))::INTEGER AS total,
                    (SUM(sub.entitlement_amount) - SUM(sub.postponed_amount)) AS total_value
                FROM (
                    -- Part 1: REPORTED payslips (linked to a finalized report)
                    SELECT
                        ps.l10n_be_meal_vouchers_report_id AS report_id,
                        ps.company_id,
                        mvr.year AS year,
                        mvr.month AS month,
                        psl.employee_id,
                        CASE WHEN EXTRACT(MONTH FROM ps.date_from)::TEXT = mvr.month
                              AND EXTRACT(YEAR FROM ps.date_from)::TEXT = mvr.year
                            THEN psl.quantity * SIGN(psl.amount)
                            ELSE 0
                        END AS entitlement,
                        CASE WHEN EXTRACT(MONTH FROM ps.date_from)::TEXT != mvr.month
                              OR EXTRACT(YEAR FROM ps.date_from)::TEXT != mvr.year
                            THEN -psl.quantity * SIGN(psl.amount)
                            ELSE 0
                        END AS postponed,
                        CASE WHEN EXTRACT(MONTH FROM ps.date_from)::TEXT = mvr.month
                              AND EXTRACT(YEAR FROM ps.date_from)::TEXT = mvr.year
                            THEN psl.quantity * SIGN(psl.amount) * ver.meal_voucher_amount
                            ELSE 0
                        END AS entitlement_amount,
                        CASE WHEN EXTRACT(MONTH FROM ps.date_from)::TEXT != mvr.month
                              OR EXTRACT(YEAR FROM ps.date_from)::TEXT != mvr.year
                            THEN -psl.quantity * SIGN(psl.amount) * ver.meal_voucher_amount
                            ELSE 0
                        END AS postponed_amount
                    FROM hr_payslip_line psl
                    JOIN hr_payslip ps ON psl.slip_id = ps.id
                    JOIN hr_salary_rule sr ON psl.salary_rule_id = sr.id
                    JOIN hr_version ver ON ps.version_id = ver.id
                    JOIN l10n_be_meal_vouchers_report mvr
                        ON ps.l10n_be_meal_vouchers_report_id = mvr.id
                    WHERE sr.code = 'MEAL_V_EMP'
                      AND ps.state in ('validated', 'paid')
                      AND ps.l10n_be_meal_vouchers_report_id IS NOT NULL

                    UNION ALL

                    -- Part 2: UNREPORTED payslips → entitlement in their own month
                    SELECT
                        NULL::INTEGER AS report_id,
                        ps.company_id,
                        EXTRACT(YEAR FROM ps.date_from)::TEXT AS year,
                        EXTRACT(MONTH FROM ps.date_from)::TEXT AS month,
                        psl.employee_id,
                        psl.quantity * SIGN(psl.amount) AS entitlement,
                        0 AS postponed,
                        psl.quantity * SIGN(psl.amount) * ver.meal_voucher_amount AS entitlement_amount,
                        0 AS postponed_amount
                    FROM hr_payslip_line psl
                    JOIN hr_payslip ps ON psl.slip_id = ps.id
                    JOIN hr_salary_rule sr ON psl.salary_rule_id = sr.id
                    JOIN hr_version ver ON ps.version_id = ver.id
                    WHERE sr.code = 'MEAL_V_EMP'
                      AND ps.state IN ('validated', 'paid')
                      AND ps.l10n_be_meal_vouchers_report_id IS NULL

                    UNION ALL

                    -- Part 3: UNREPORTED payslips mapped to draft/ready reports
                    SELECT
                        NULL::INTEGER AS report_id,
                        ps.company_id,
                        mvr.year AS year,
                        mvr.month AS month,
                        psl.employee_id,
                        0 AS entitlement,
                        -psl.quantity * SIGN(psl.amount) AS postponed,
                        0 AS entitlement_amount,
                        -psl.quantity * SIGN(psl.amount) * ver.meal_voucher_amount AS postponed_amount
                    FROM hr_payslip_line psl
                    JOIN hr_payslip ps ON psl.slip_id = ps.id
                    JOIN hr_salary_rule sr ON psl.salary_rule_id = sr.id
                    JOIN hr_version ver ON ps.version_id = ver.id
                    JOIN l10n_be_meal_vouchers_report mvr
                       ON mvr.state IN ('draft', 'ready')
                       AND (
                           mvr.year::INTEGER > EXTRACT(YEAR FROM ps.date_from)
                           OR (
                               mvr.year::INTEGER = EXTRACT(YEAR FROM ps.date_from)
                               AND mvr.month::INTEGER > EXTRACT(MONTH FROM ps.date_from)
                           )
                       )
                    JOIN res_company rc_payslip ON rc_payslip.id = ps.company_id
                    JOIN res_company rc_report
                        ON rc_report.id = mvr.company_id
                        AND rc_payslip.parent_path LIKE rc_report.parent_path || '%%'
                    WHERE sr.code = 'MEAL_V_EMP'
                      AND ps.state IN ('validated', 'paid')
                      AND ps.l10n_be_meal_vouchers_report_id IS NULL
                ) sub
                GROUP BY sub.report_id, sub.company_id, sub.year, sub.month, sub.employee_id
            );
        """, SQL.identifier(self._table))
        self.env.cr.execute(statement)

    def _get_corrected_payslips(self):
        self.ensure_one()
        if not self.year or not self.month:
            return self.env['hr.payslip']
        report_year = int(self.year)
        report_month = int(self.month)
        current_month_start = date(report_year, report_month, 1)
        if self.report_id and self.report_id.state == 'done':
            payslips = self.env['hr.payslip'].search(_get_payslips_domain(
                branch_ids=self.report_id.branch_ids,
                employee_id=self.employee_id.id,
                date_from=None,
                prev_date_from=current_month_start,
                report_id=self.report_id.id,
            ))
            line_values = payslips._get_line_values(['MEAL_V_EMP'])
            return payslips.filtered(lambda p: line_values['MEAL_V_EMP'][p.id]['total'] < 0)

        payslips = self.env['hr.payslip'].search(_get_payslips_domain(
            branch_ids=self.report_id.branch_ids,
            employee_id=self.employee_id.id,
            date_from=None,
            prev_date_from=current_month_start,
            report_id=False))
        line_values = payslips._get_line_values(['MEAL_V_EMP'])
        return payslips.filtered(lambda p: line_values['MEAL_V_EMP'][p.id]['total'] < 0)

    def action_open_corrected_payslips(self):
        self.ensure_one()
        corrected_payslips = self._get_corrected_payslips()
        action = self.env['ir.actions.act_window']._for_xml_id('hr_payroll.action_view_hr_payslip_month_form')
        action['domain'] = [('id', 'in', corrected_payslips.ids)]
        return action


def _get_payslips_domain(branch_ids, date_from=None, employee_id=None, prev_date_from=None, date_to=None, report_id=None):
    domain = [
        ('company_id', 'in', branch_ids),
        ('state', 'in', ['validated', 'paid']),
        ('line_ids.salary_rule_id.code', '=', 'MEAL_V_EMP'),
    ]
    if date_from:
        domain.append(('date_from', '>=', date_from))
    if employee_id:
        domain.append(('employee_id', '=', employee_id))
    if prev_date_from:
        domain.append(('date_from', '<', prev_date_from))
    if date_to:
        domain.append(('date_to', '<=', date_to))
    if report_id is False:
        domain.append(('l10n_be_meal_vouchers_report_id', '=', False))
    elif report_id is not None:
        domain.append(('l10n_be_meal_vouchers_report_id', '=', report_id))
    return domain
