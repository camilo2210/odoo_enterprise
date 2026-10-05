# Part of Odoo. See LICENSE file for full copyright and licensing details.
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools.date_utils import start_of
from odoo.tools.misc import formatLang

from dateutil.relativedelta import relativedelta


class HrSalaryAttachment(models.Model):
    _name = 'hr.salary.attachment'
    _description = 'Payslip Adjustment'
    _inherit = ['mail.thread']
    _rec_name = 'description'
    _order = 'state, sequence'

    _check_amount = models.Constraint(
        'CHECK (amount > 0)',
        'Oops! Let’s keep the payslip amount strictly positive. We want to deduct money from our employee’s payslip, not add to it!'
    )
    _check_remaining_amount = models.Constraint(
        'CHECK (remaining_amount >= 0)',
        "Remaining amount must be positive.",
    )
    _check_dates = models.Constraint(
        'CHECK (date_start <= date_end)',
        "End date may not be before the starting date.",
    )

    sequence = fields.Integer(default=1, index=True, required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index='btree',
                                    domain=lambda self: [('company_id', 'in', self.env.companies.ids)])
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    description = fields.Char(string="Note")
    structure_type_id = fields.Many2one(
        related='employee_id.version_id.structure_type_id',
        groups="hr_payroll.group_hr_payroll_user",
    )
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string="Salary Rule",
        required=True,
        index=True,
        tracking=True,
        # Only rules reachable by the employee's payslips: usable as payslip input and
        # belonging to a structure of the employee's structure type.
        domain="[('input_usage_payslip', '=', True), ('struct_ids.type_id', '=', structure_type_id)]",
    )
    user_instructions = fields.Html(compute='_compute_user_instructions')
    salary_rule_warning = fields.Char(compute='_compute_salary_rule_warning')
    is_recurring = fields.Boolean('Repeat', help='Define if the amount must be repeated on every payslip until a specific date.')
    amount = fields.Monetary('Amount', required=True, tracking=True, help='Amount to pay each payslip.')
    paid_amount = fields.Monetary('Paid Amount', tracking=True, copy=False)
    remaining_amount = fields.Monetary(
        'Remaining Amount', compute='_compute_remaining_amount', store=True,
        help='Remaining amount to be paid.',
    )
    remaining_time = fields.Char(
        'Remaining Time', compute='_compute_remaining_time', help='Remaining time to be paid.'
    )
    date_start = fields.Date('Start Date', required=True, default=lambda r: start_of(fields.Date.context_today(r), 'month'), tracking=True)
    date_estimated_end = fields.Date(
        'Estimated End Date',
        help='Approximated end date.',
    )
    date_end = fields.Date(
        'End Date', default=False, tracking=True,
        help='Date at which this payslip adjustment has been set as completed.',
    )
    state = fields.Selection(
        selection=[
            ('1_open', 'Running'),
            ('2_close', 'Done'),
        ],
        string='Status',
        default='1_open',
        required=True,
        tracking=True,
        copy=False,
    )
    payslip_ids = fields.Many2many('hr.payslip', relation='hr_payslip_hr_salary_attachment_rel', string='Payslips', copy=False)
    payslip_count = fields.Integer('# Payslips', compute='_compute_payslip_count')
    has_done_payslip = fields.Boolean(compute="_compute_has_done_payslip")

    attachment = fields.Binary('Document', copy=False)
    attachment_name = fields.Char()

    has_similar_attachment = fields.Boolean(compute='_compute_has_similar_attachment')
    has_similar_attachment_warning = fields.Char(compute='_compute_has_similar_attachment')

    is_seized = fields.Boolean(string="Is Seized", compute='_compute_is_seized')
    beneficiary_bank_account_id = fields.Many2one(
        'res.partner.bank',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        index='btree_not_null',
        string='Beneficiary',
        help="Used by payment reports to send negative adjustments (e.g. child support) directly to the beneficiary account.")
    allow_out_payment = fields.Boolean(related='beneficiary_bank_account_id.allow_out_payment', string="Can be used for outgoing payments")
    country_id = fields.Many2one('res.country', string='Country', related='company_id.country_id')
    country_code = fields.Char(related='country_id.code', depends=['country_id'], readonly=True)

    @api.constrains('date_start', 'date_estimated_end')
    def _check_start_estimated_end_dates(self):
        for attachment in self:
            if attachment.date_estimated_end and attachment.date_start > attachment.date_estimated_end:
                raise UserError(self.env._("The starting date cannot be after the estimated end date."))

    @api.depends('salary_rule_id')
    def _compute_is_seized(self):
        seized_categories = self.env['hr.salary.rule.category']._get_seized_categories()
        for attachment in self:
            attachment.is_seized = bool(set(attachment.salary_rule_id.category_ids.ids) & set(seized_categories.ids))

    @api.depends('salary_rule_id', "employee_id.display_name")
    def _compute_display_name(self):
        for attachment in self:
            display_name = attachment.employee_id.display_name
            attachment_type = attachment.salary_rule_id.display_name
            attachment.display_name = self.env._(
                "%(display_name)s %(attachment_type)s",
                display_name=display_name if display_name else "",
                attachment_type=attachment_type if attachment_type else ""
            )

    @api.depends('is_recurring', 'date_estimated_end', 'date_end', 'date_start')
    def _compute_remaining_time(self):
        for attachment in self:
            date_end = attachment.date_estimated_end or attachment.date_end
            if not attachment.is_recurring or not date_end or not attachment.date_start:
                attachment.remaining_time = False
                continue

            delta = relativedelta(date_end + relativedelta(days=1), attachment.date_start)

            if not (delta.years > 0 or delta.months > 0 or delta.days > 0):
                attachment.remaining_time = False
                continue

            duration = []
            if delta.years:
                duration.append(self.env._("%(years)s years", years=delta.years))
            if delta.months:
                duration.append(self.env._("%(months)s months", months=delta.months))
            if delta.days:
                duration.append(self.env._("%(days)s days", days=delta.days))

            attachment.remaining_time = ' & '.join(duration)

    @api.depends('paid_amount', 'amount', 'is_recurring')
    def _compute_remaining_amount(self):
        for record in self:
            if record.is_recurring:
                record.remaining_amount = record.amount
            else:
                record.remaining_amount = max(0, record.amount - record.paid_amount)

    @api.depends('payslip_ids')
    def _compute_payslip_count(self):
        for record in self:
            record.payslip_count = len(record.payslip_ids)

    @api.depends('employee_id', 'amount', 'date_start', 'is_recurring', 'salary_rule_id', 'beneficiary_bank_account_id')
    def _compute_has_similar_attachment(self):
        date_min = min(self.mapped('date_start'))
        possible_matches = self.search([
            ('state', '=', '1_open'),
            ('employee_id', 'in', self.employee_id.ids),
            ('amount', 'in', self.mapped('amount')),
            ('date_start', '<=', date_min),
        ])
        for record in self:
            similar = []
            if record.date_start and record.state == '1_open':
                similar = possible_matches.filtered_domain([
                    ('id', '!=', record.id or record._origin.id),
                    ('employee_id', '=', record.employee_id.id),
                    ('amount', '=', record.amount),
                    ('is_recurring', '=', record.is_recurring),
                    ('beneficiary_bank_account_id', '=', record.beneficiary_bank_account_id.id),
                    ('date_start', '<=', record.date_start),
                    ('salary_rule_id', '=', record.salary_rule_id.id),
                ])
            record.has_similar_attachment = similar if record.state == '1_open' else False
            record.has_similar_attachment_warning = similar and self.env._('Warning, a similar attachment has been found.')

    @api.depends('salary_rule_id', 'employee_id')
    def _compute_salary_rule_warning(self):
        # Payslips only take an adjustment into account when their structure holds a rule
        # with the same code flagged "Available on Payslip"; warn when no structure of
        # the employee's structure type does, as the adjustment would silently have no effect.
        for attachment in self:
            attachment.salary_rule_warning = False
            structure_type = attachment.employee_id.version_id.structure_type_id
            if not attachment.salary_rule_id or not structure_type:
                continue
            structs = self.env['hr.payroll.structure'].search([('type_id', '=', structure_type.id)])
            attachment_codes = structs.rule_ids.filtered('input_usage_payslip').mapped('code')
            if attachment.salary_rule_id.code not in attachment_codes:
                attachment.salary_rule_warning = self.env._(
                    'No rule with code %(code)s is available for adjustments in the structures of %(structure_type)s: '
                    'this adjustment will have no effect on the payslips of %(employee)s.',
                    code=attachment.salary_rule_id.code,
                    structure_type=structure_type.name,
                    employee=attachment.employee_id.name,
                )

    @api.depends("payslip_ids.state")
    def _compute_has_done_payslip(self):
        for record in self:
            record.has_done_payslip = any(payslip.state in ['validated', 'paid'] for payslip in record.payslip_ids)

    @api.depends('salary_rule_id.user_instructions', 'salary_rule_id.name')
    def _compute_user_instructions(self):
        for attachment in self:
            if not attachment.salary_rule_id.user_instructions:
                attachment.user_instructions = False
                continue
            attachment.user_instructions = Markup("<h2><i class='oi text-info' data-icon='info'/> %s</h2>%s") % (
                attachment.salary_rule_id.name,
                attachment.salary_rule_id.user_instructions or '',
            )

    @api.model_create_multi
    def create(self, vals_list):
        # Clear estimated end date if the attachment is not recurring
        for vals in vals_list:
            if not vals.get('is_recurring'):
                vals['date_estimated_end'] = False

        records = super().create(vals_list)
        if self.env.context.get('install_mode'):
            # Module/demo data loads must not recompute payslips: rules of sibling
            # modules may not be reloaded yet at this point of an upgrade.
            return records

        record_domains = []
        for record in records:
            domain = [
                ('employee_id', '=', record.employee_id.id),
                ('date_to', '>=', record.date_start),
            ]
            if record.date_end:
                domain.append(('date_from', '<=', record.date_end))
            record_domains.append(domain)

        if not record_domains:
            return records

        search_domain = Domain.AND([
            [('state', '=', 'draft')],
            Domain.OR(record_domains),
        ])
        payslips_to_recompute = self.env['hr.payslip'].search(search_domain)
        if payslips_to_recompute:
            payslips_to_recompute.compute_sheet()
        return records

    def write(self, vals):
        # Clear estimated end date if is_recurring is set to False
        if 'is_recurring' in vals and not vals['is_recurring']:
            vals['date_estimated_end'] = False

        res = super().write(vals)
        if self.env.context.get('install_mode'):
            # Module/demo data loads must not recompute payslips: rules of sibling
            # modules may not be reloaded yet at this point of an upgrade.
            return res
        payslips_to_recompute = self.payslip_ids.filtered(lambda p: p.state == 'draft')
        if payslips_to_recompute:
            payslips_to_recompute.compute_sheet()
        return res

    def action_close(self):
        payslips_to_recompute = self.payslip_ids.filtered(lambda p: p.state in ['draft', 'validated'])
        today = fields.Date.context_today(self)
        self.write({
            'state': '2_close',
            'date_end': today,
        })
        if payslips_to_recompute:
            payslips_to_recompute._compute_issues()

    def action_open(self):
        self.ensure_one()
        self.write({
            'state': '1_open',
            'date_end': False,
        })

    def action_open_payslips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Payslips'),
            'res_model': 'hr.payslip',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.payslip_ids.ids)],
        }

    def action_open_employee_salary_attachment(self):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('New Payslip Adjustment') if self.env.context.get("new") else self.env._('Edit Payslip Adjustment'),
            'views': [[self.env.ref("hr_payroll.hr_salary_attachment_view_form").id, "form"]],
            'res_id': False if self.env.context.get("new") else self.id,
            'res_model': 'hr.salary.attachment',
            'context': {
                **self.env.context,
            }
        }

    @api.ondelete(at_uninstall=False)
    def _unlink_if_not_running(self):
        if any(assignment.state == '1_open' for assignment in self):
            raise UserError(self.env._(
                "The payslip adjustment you're trying to remove is still running. You can't delete unless you change it to completed or cancelled."
            ))

    @api.ondelete(at_uninstall=False)
    def unlink_if_not_linked_in_payslips(self):
        if any(attachment.payslip_ids for attachment in self):
            raise UserError(self.env._('You cannot delete a payslip adjustment that is linked to a payslip!'))

    def _get_payment_amount(self, total_amount):
        res = {}
        remaining = total_amount
        for attachment in self:
            amount = min(attachment.remaining_amount, remaining)
            if not amount:
                continue
            remaining -= amount
            res[attachment] = amount
        # If we still have remaining, balance the attachments (running) that have a total amount
        # in the chronology of estimated end dates.
        if not remaining:
            return res

        raise UserError(self.env._('The total amount to pay is higher than the total remaining amount of the selected payslip adjustments.'))

    def record_payment(self, payslip, total_amount):
        ''' Record a new payment for this attachment, if the total has been reached the attachment will be closed.

        :param payslip: the payslip in which an amount of this attachment is paid
        :param total_amount: amount to register for this payment
            computed using the payslip_amount and the total if not given

        Note that paid_amount can never be higher than total_amount
        '''
        def _record_payment(attachment, payslip, amount):
            if amount == 0:
                return
            attachment.message_post(
                body=self.env._('Recorded a new payment of %(amount)s in this %(payslip)s.',
                    payslip=Markup("<a href='#' data-oe-model='hr.payslip' data-oe-id='{payslip_id}'>Payslip</a>")
                    .format(payslip_id=payslip.id),
                    amount=formatLang(self.env, amount, currency_obj=attachment.currency_id)),
            )
            attachment.paid_amount += amount
            if attachment.remaining_amount == 0:
                attachment.action_close()

        def _record_priority_payment(attachments, payslip, amount, cap_func):
            # Compute caps for each record
            caps = [cap_func(rec) for rec in attachments]
            total_need = sum(caps)
            if not total_need:
                return amount

            if total_need <= amount:
                # We can pay all the monthly amounts
                for attachment, cap in zip(attachments, caps):
                    if not cap:
                        continue
                    amount -= cap
                    _record_payment(attachment, payslip, cap)
                return amount
            # We need to prorate the payment
            for attachment, cap in zip(attachments, caps):
                if not cap:
                    continue
                pay_amount = min(amount * cap / total_need, cap)
                _record_payment(attachment, payslip, pay_amount)
            return 0

        assert payslip
        remaining = total_amount
        attachments_by_priority = self.grouped('sequence')
        for _priority, attachments in attachments_by_priority.items():
            # Compute caps for each record
            remaining = _record_priority_payment(attachments, payslip, remaining, lambda r: r.remaining_amount)

        if remaining:
            raise UserError(self.env._('The total amount to pay is higher than the total remaining amount of the selected payslip adjustments.'))

    def _get_active_amount(self):
        return sum(a.remaining_amount for a in self)
