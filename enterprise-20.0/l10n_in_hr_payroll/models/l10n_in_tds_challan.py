# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from .utils import format_amount


class L10nInTDSChallan(models.Model):
    _name = 'l10n.in.tds.challan'
    _description = 'TDS Challan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'paid_date desc, id desc'

    def _compute_display_name(self):
        for challan in self:
            if challan.challan_number:
                challan.display_name = self.env._("Challan #%(challan_number)s", challan_number=challan.challan_number)
            else:
                challan.display_name = self.env._("New Challan")

    @api.model
    def _default_challan_date_from(self):
        return fields.Date.context_today(self) + relativedelta(day=1, months=-1)

    @api.model
    def _default_challan_date_to(self):
        return fields.Date.context_today(self) + relativedelta(day=31, months=-1)

    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string="Company", required=True, readonly=True,
        default=lambda self: self.env.company,
    )
    challan_date_from = fields.Date("From", default=_default_challan_date_from, required=True, tracking=True)
    challan_date_to = fields.Date("To", default=_default_challan_date_to, required=True, tracking=True)
    paid_date = fields.Date(string="Paid Date", required=True, default=fields.Date.context_today, tracking=True)
    challan_number = fields.Char(string="Challan Number", required=True, tracking=True)
    bsr_code = fields.Char(string="BSR Code", required=True, tracking=True)

    currency_id = fields.Many2one(related='company_id.currency_id')
    tds_amount = fields.Monetary(string="TDS Amount", compute='_compute_tds_amount', store=True)
    interest = fields.Monetary(string="Interest")
    penalty = fields.Monetary(string="Penalty")
    fee = fields.Monetary(string="Fees")
    total_paid = fields.Monetary(string="Total Paid", compute='_compute_total_paid', store=True)

    state = fields.Selection(selection=[
        ('draft', "Draft"),
        ('done', "Done"),
    ], string="State", default='draft', required=True, tracking=True)
    minor_head = fields.Selection(
        selection=[
            ('200', "200 - TDS payable by taxpayer"),
            ('400', "400 - TDS regular assessment"),
        ],
        string="Minor Head",
        default='200',
        required=True,
        help="""200 - TDS Payable by Taxpayer: Select when depositing TDS deducted and payable to the government.
400 - TDS Regular Assessment: Select when making payments for TDS demand, interest, penalty, or other assessment-related dues.""",
    )
    mode_of_payment = fields.Selection(
        selection=[
            ('B', "Transfer Voucher"),
            ('C', "Bank Challan"),
        ],
        string="Mode of Payment", default='C', required=True,
        help="""Choose 'Bank Challan' if paid through a regular bank challan or
'Transfer Voucher' if tax is paid via Book Adjustment (applicable only for Government deductors).""",
    )
    challan_line_ids = fields.One2many('l10n.in.tds.challan.line', 'challan_id', string="Challan Lines")
    form_138_id = fields.Many2one('l10n.in.payroll.form.138', "Form 138", compute='_compute_form_138_id', store=True)

    financial_year_start = fields.Integer(
        compute="_compute_financial_year_start",
        store=True,
    )

    @api.constrains('challan_number', 'bsr_code')
    def _check_challan_bsr_length(self):
        for rec in self:
            if rec.challan_number and len(rec.challan_number.strip()) != 5:
                raise UserError(self.env._("Challan Number must be exactly 5 characters long."))
            if rec.bsr_code and len(rec.bsr_code.strip()) != 7:
                raise UserError(self.env._("BSR Code must be exactly 7 characters long."))

    @api.depends('challan_date_from', 'challan_date_to', 'company_id')
    def _compute_form_138_id(self):
        self.form_138_id = False
        form_138_by_company = dict(self.env['l10n.in.payroll.form.138']._read_group(
            domain=[
                ('company_id', 'in', self.company_id.ids),
                ('state', '!=', 'done'),
                ('quarter_date_start', '<=', max(self.mapped('challan_date_from'))),
                ('quarter_date_end', '>=', min(self.mapped('challan_date_to'))),
            ],
            groupby=['company_id'],
            aggregates=['id:recordset'],
        ))

        for challan in self:
            challan.form_138_id = form_138_by_company.get(challan.company_id, self.env['l10n.in.payroll.form.138']).filtered(
                lambda form: form.quarter_date_start <= challan.challan_date_from and form.quarter_date_end >= challan.challan_date_to,
            )[:1]

    @api.depends('challan_line_ids')
    def _compute_tds_amount(self):
        for challan in self:
            challan.tds_amount = sum(challan.challan_line_ids.mapped('total_tds_paid'))

    @api.depends('tds_amount', 'penalty', 'interest', 'fee')
    def _compute_total_paid(self):
        for challan in self:
            challan.total_paid = challan.tds_amount + challan.penalty + challan.interest + challan.fee

    @api.depends('challan_date_from')
    def _compute_financial_year_start(self):
        for challan in self:
            if challan.challan_date_from:
                challan.financial_year_start = challan.challan_date_from.year if challan.challan_date_from.month >= 4 else challan.challan_date_from.year - 1

    @api.model
    def default_get(self, fields):
        if self.env.company.country_id.code != "IN":
            raise UserError(self.env._('You must be logged in a Indian company to use this feature'))
        return super().default_get(fields)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_done_nor_in_form_138(self):
        for challan in self:
            if challan.state == 'done':
                raise UserError(self.env._("You cannot delete TDS challan record in done state."))

    def action_open_payslip_import(self):
        self.ensure_one()
        return {
            'name': self.env._('Import Payslips'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'views': [(self.env.ref('l10n_in_hr_payroll.l10n_in_tds_challan_payslip_view_list').id, 'list')],
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('date_from', '>=', self.challan_date_from),
                ('date_to', '<=', self.challan_date_to),
                ('state', '=', 'paid'),
                ('is_refund_payslip', '=', False),
            ],
            'target': 'new',
            'context': {
                'challan_id': self.id,
            },
        }

    def action_import_payslips(self, payslip_ids):
        self.ensure_one()
        payslips = self.env['hr.payslip'].browse(payslip_ids)
        line_values_by_payslip_id = payslips._l10n_in_prepare_challan_line_values_from_payslips()
        challan_line_by_payslip_id = self.challan_line_ids.grouped('payslip_id')
        commands = []
        for payslip in payslips:
            line_values = line_values_by_payslip_id.get(payslip)
            challan_line = challan_line_by_payslip_id.pop(payslip, None)
            if line_values:
                if challan_line:
                    commands.append(Command.update(challan_line.id, {
                        'total_tds_paid': line_values_by_payslip_id[payslip],
                    }))
                else:
                    commands.append(Command.create({
                        'total_tds_paid': line_values_by_payslip_id[payslip],
                        'payslip_id': payslip.id,
                    }))
        if commands:
            self.challan_line_ids = commands

    def action_mark_as_done(self):
        if any(not challan.challan_line_ids for challan in self):
            raise UserError(self.env._("Cannot mark challan as done with 0 challan lines."))
        self.state = 'done'

    def action_set_to_draft(self):
        self.state = 'draft'
        if self.form_138_id:
            self.form_138_id.action_set_to_draft()

    def action_open_form_138(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n.in.payroll.form.138',
            'views': [[False, 'form']],
            'target': 'current',
            'res_id': self.form_138_id.id,
        }

    def _get_challan_amounts(self):
        self.ensure_one()
        employee_total_tds = sum(self.challan_line_ids.mapped('total_tds_paid'))
        deposit_amount = self.tds_amount + self.interest + self.penalty + self.fee

        return {
            'interest': self.interest,
            'others': self.penalty,
            'fee': self.fee,
            'deposit_amount': deposit_amount,
            'deductee_deposit_amount': self.tds_amount,
            'deductee_total_tds': employee_total_tds,
        }

    def _prepare_cd_record(self, line_number, challan_sequence):
        """Prepare the Form 138 Challan Detail (CD) record containing the challan's
        payment identifiers and deposited tax amounts.

        Format reference: https://tinpan.proteantech.in/downloads/e-tds/eTDS-download-regular.html
        """
        self.ensure_one()
        amounts = self._get_challan_amounts()
        return [
            str(line_number),  # Line Number
            'CD',  # Record Type
            '1',  # Batch Number
            str(challan_sequence),  # Challan-Detail Record Number
            str(len(self.challan_line_ids)),  # Count of Deductee / Party Records
            'N',  # NIL Challan Indicator
            '',  # Challan Updation Indicator (not applicable)
            format_amount(amounts['deductee_total_tds']),  # Total tax deducted
            format_amount(amounts['interest']),  # Total interest
            format_amount(amounts['fee']),  # Total fee
            format_amount(amounts['others']),  # Total penalty
            format_amount(amounts['deposit_amount']),  # Total of Deposit Amount as per Challan
            self.mode_of_payment,  # Mode of payment of tax
            '',  # Last BSR Code / Form 24G Receipt Number (not applicable)
            self.bsr_code,  # Bank-Branch Code / Form 24G Receipt Number
            '',  # Last Bank Challan No/DDO Serial Number (not applicable)
            self.challan_number,  # Bank Challan No/DDO Serial Number
            '',  # Last Date of Bank Challan No/DDO Serial Number (not applicable)
            format_date(self.env, self.paid_date, date_format='ddMMY'),  # Date of Bank Challan / Transfer Voucher
            '',  # Last Total of Deposit Amount as per Challan (not applicable)
            format_amount(amounts['deductee_deposit_amount']),  # Total Tax Deposited Amount as per Employee/Deductee annexure
            format_amount(amounts['deductee_total_tds']),  # Total Tax Deducted Amount as per Employee/Deductee annexure
            self.minor_head,  # Minor Head of Challan
            '',  # Filler 1
            '',  # Filler 2
            '',  # Filler 3
            '',  # Filler 4
            '',  # Filler 5
            '',  # Filler 6
            '',  # Record Hash (not applicable)
        ]
