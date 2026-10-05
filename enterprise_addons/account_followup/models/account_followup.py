# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Account_FollowupFollowupLine(models.Model):
    _name = 'account_followup.followup.line'
    _description = 'Follow-up Criteria'
    _order = 'delay asc'
    _check_company_auto = True

    delay = fields.Integer(
        string='Signed Delay',
        default=5,
    )
    display_delay = fields.Integer(
        string='Due Days',
        required=True,
        compute='_compute_display_delay',
        inverse='_inverse_display_delay_and_timing',
        help="The number of days after or before the due date of the invoice to wait before sending the reminder.",
    )
    reminder_timing = fields.Selection(
        selection=[
            ('before', 'before'),
            ('after', 'after'),
        ],
        string='Reminder Timing',
        required=True,
        compute='_compute_reminder_timing',
        inverse='_inverse_display_delay_and_timing',
        help="Indicates whether the reminder should be sent before or after the invoice due date.",
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    mail_template_id = fields.Many2one(
        comodel_name='mail.template',
        domain="[('model', '=', 'res.partner')]",
        default=lambda self: self.env.ref('account_followup.mail_template_partner_payment_kind_reminder', raise_if_not_found=False),
    )
    send_email = fields.Boolean(
        string='Email',
        default=True,
    )

    sms_template_id = fields.Many2one(
        comodel_name='sms.template',
        domain="[('model', '=', 'res.partner')]",
    )
    send_sms = fields.Boolean(string='SMS')

    create_activity = fields.Boolean(string='Schedule Activity')
    activity_summary = fields.Char(string='Summary')
    activity_note = fields.Text(string='Note')
    activity_type_id = fields.Many2one(
        comodel_name='mail.activity.type',
        string='Activity Type',
        default=False,
    )
    activity_default_responsible_type = fields.Selection(
        selection=[
            ('followup', 'Reminder Responsible'),
            ('salesperson', 'Salesperson'),
            ('account_manager', 'Account Manager'),
        ],
        string='Responsible',
        default='followup',
        required=True,
        help="Determine who will be assigned to the activity:\n"
             "- Follow-up Responsible (default)\n"
             "- Salesperson: Sales Person defined on the invoice\n"
             "- Account Manager: Sales Person defined on the customer",
    )

    _days_uniq = models.Constraint(
        'unique(company_id, delay)',
        "There can only be one reminder level with a given delay (per company)",
    )

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        default = dict(default or {})
        company_ids = [self.company_id.id]
        if 'company_id' in default:
            company_ids += default['company_id']

        highest_delay_per_company_id = {
            company.id: delay_max
            for company, delay_max in self._read_group(
                domain=[('company_id', 'in', company_ids)],
                groupby=['company_id'],
                aggregates=['delay:max'],
            )
        }
        for line, vals in zip(self, vals_list):
            if 'delay' not in default:
                # If several records from the same company are copied in batch, we need to ensure that their delay aren't
                # set to the same value, we offset it by highest existing delay + 15 arbitrary days (cumulative).
                company_id = default.get('company_id', line.company_id.id)
                highest_delay_per_company_id[company_id] += 15
                vals['delay'] = highest_delay_per_company_id[company_id]
        return vals_list

    @api.constrains('display_delay')
    def _check_positive_display_delay(self):
        if any(line.display_delay < 0 for line in self):
            raise ValidationError(self.env._('Delay must be a positive value. To send a reminder before the invoice due date, set the Reminder Timing to "Before" and enter a positive delay.'))

    @api.depends('display_delay', 'reminder_timing')
    def _compute_display_name(self):
        reminder_timing_label = dict(self._fields['reminder_timing']._description_selection(self.env))
        for record in self:
            record.display_name = self.env._(
                "%(display_delay)s days %(reminder_timing)s",
                display_delay=record.display_delay,
                reminder_timing=reminder_timing_label[record.reminder_timing],
            )

    @api.depends('delay')
    def _compute_display_delay(self):
        for line in self:
            line.display_delay = abs(line.delay)

    @api.depends('delay')
    def _compute_reminder_timing(self):
        for line in self:
            line.reminder_timing = 'before' if line.delay < 0 else 'after'

    def _inverse_display_delay_and_timing(self):
        for line in self:
            line.delay = -line.display_delay if line.reminder_timing == 'before' else line.display_delay
