# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.fields import Domain


class HelpdeskTicket(models.Model):
    _name = 'helpdesk.ticket'
    _inherit = 'helpdesk.ticket'

    def _default_team_id(self):
        if project_id := self.env.context.get('default_project_id'):
            if team_id := self.env['helpdesk.team'].search([('project_id', '=', project_id)], limit=1).id:
                return team_id

        return super()._default_team_id()

    team_id = fields.Many2one(domain="[('use_helpdesk_timesheet', '=', True)] if context.get('default_project_id') else []")
    project_id = fields.Many2one(
        "project.project", related="team_id.project_id", readonly=True, store=True, index='btree_not_null')
    timesheet_ids = fields.One2many('account.analytic.line', 'helpdesk_ticket_id', 'Timesheets',
        help="Time spent on this ticket. By default, your timesheets will be linked to the sales order item of your ticket.\n"
             "Remove the sales order item to make your timesheet entries non billable.")
    use_helpdesk_timesheet = fields.Boolean('Timesheet activated on Team', related='team_id.use_helpdesk_timesheet', readonly=True)
    total_hours_spent = fields.Float("Time Spent", compute='_compute_total_hours_spent', default=0, compute_sudo=True, store=True)
    encode_uom_in_days = fields.Boolean(compute='_compute_encode_uom_in_days', export_string_translation=False)
    analytic_account_id = fields.Many2one('account.analytic.account',
        compute='_compute_analytic_account_id', store=True, readonly=False,
        string='Analytic Account', domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")

    def _compute_encode_uom_in_days(self):
        self.encode_uom_in_days = self.env.company.timesheet_encode_uom_id == self.env.ref('uom.product_uom_day')

    @api.depends('timesheet_ids.unit_amount')
    def _compute_total_hours_spent(self):
        if not any(self._ids):
            for ticket in self:
                ticket.total_hours_spent = sum(ticket.timesheet_ids.mapped('unit_amount'))
            return
        timesheet_read_group = self.env['account.analytic.line']._read_group(
            [('helpdesk_ticket_id', 'in', self.ids)],
            ['helpdesk_ticket_id'],
            ['unit_amount:sum'],
        )
        timesheets_per_ticket = {helpdesk_ticket.id: unit_amount_sum for helpdesk_ticket, unit_amount_sum in timesheet_read_group}
        for ticket in self:
            ticket.total_hours_spent = timesheets_per_ticket.get(ticket.id, 0.0)

    @api.onchange('team_id')
    def _onchange_team_id(self):
        # If the new helpdesk team has no timesheet feature AND ticket has non-validated timesheets, show a warning message
        if (
            self.timesheet_ids and
            not self.team_id.use_helpdesk_timesheet and
            not all(t.validated for t in self.timesheet_ids)
        ):
            return {
                'warning': {
                    'title': _("Warning"),
                    'message': _("Moving this task to a helpdesk team without timesheet support will retain timesheet drafts in the original helpdesk team. "
                                 "Although they won't be visible here, you can still edit them using the Timesheets app."),
                    'type': "notification",
                },
            }

    @api.model_create_multi
    def create(self, vals_list):
        default_project_id = self.env.context.get('default_project_id')
        for vals in vals_list:
            project_id = vals.get('project_id') or default_project_id
            if not vals.get('team_id') and project_id:
                project = self.env['project.project'].browse(project_id)
                if project.helpdesk_team:
                    vals['team_id'] = project.helpdesk_team[0].id
        return super().create(vals_list)

    @api.depends('project_id')
    def _compute_analytic_account_id(self):
        for ticket in self:
            ticket.analytic_account_id = ticket.project_id.account_id

    @api.depends('use_helpdesk_timesheet')
    def _compute_display_extra_info(self):
        if self.env.user.has_group('analytic.group_analytic_accounting'):
            show_analytic_account_id_records = self.filtered('use_helpdesk_timesheet')
            show_analytic_account_id_records.display_extra_info = True
            super(HelpdeskTicket, self - show_analytic_account_id_records)._compute_display_extra_info()
        else:
            super()._compute_display_extra_info()

    def write(self, vals):
        res = super().write(vals)
        if vals.get('team_id'):
            timesheet_read_group = self.env['account.analytic.line']._read_group(
                [('project_id', '!=', False), ('helpdesk_ticket_id', 'in', self.ids), ('validated', '=', False)],
                ['helpdesk_ticket_id'],
                ['id:recordset'],
            )
            for ticket, timesheets in timesheet_read_group:
                if ticket.use_helpdesk_timesheet and ticket.project_id:
                    timesheets_to_update = timesheets.filtered(lambda t: t.project_id != ticket.project_id)
                    timesheets_to_update.project_id = ticket.project_id
                else:
                    timesheets.helpdesk_ticket_id = False
        return res

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        if name or not self.env.context.get('timesheet_timer_search') or not (employee := self.env.user.employee_id):
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

        timesheet_domain = [
            ('employee_id', '=', employee.id),
            ('project_id', '!=', False),
            ('project_id.allow_timesheets', '=', True),
            ('helpdesk_ticket_id', '!=', False),
        ]
        ticket_domain = Domain.AND([
            domain or [],
            [('active', '=', True)],
        ])
        if ticket_domain:
            timesheet_domain.append(('helpdesk_ticket_id', 'any', ticket_domain))
        recent_tickets = self.env['account.analytic.line']._get_recently_used_records(
            'helpdesk_ticket_id',
            domain=timesheet_domain,
        )
        if not recent_tickets:
            return super().name_search(name=name, domain=domain, operator=operator, limit=limit)

        if len(recent_tickets) >= limit:
            return recent_tickets

        recent_ticket_ids = [ticket_id for ticket_id, _display_name in recent_tickets]
        remaining_tickets = super().name_search(
            name=name,
            domain=Domain.AND([domain or [], [('id', 'not in', recent_ticket_ids)]]),
            operator=operator,
            limit=limit - len(recent_tickets)
        )
        return recent_tickets + remaining_tickets

    def action_print_timesheets(self):
        if not self.timesheet_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': self.env._('There are no timesheets to print for this ticket'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        return self.env.ref('helpdesk_timesheet.timesheet_report_ticket').report_action(self)
