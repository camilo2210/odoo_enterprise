# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import Command, models, fields, exceptions, _, api
from odoo.tools import format_date


class SaleCommissionPlanUser(models.Model):
    _name = 'sale.commission.plan.user'
    _description = 'Commission Plan User'
    _rec_name = 'user_id'
    _rec_names_search = ('user_id', 'plan_id')
    _order = 'id'

    plan_id = fields.Many2one('sale.commission.plan', required=True, index=True, ondelete='cascade')
    user_type = fields.Selection(related='plan_id.user_type')
    user_id = fields.Many2one('res.users', "Salesperson", required=True, domain="[('share', '=', False)]", index=True)
    user_ids = fields.Many2many(
        string="Sum of achievements",
        comodel_name='res.users',
        relation='com_plan_user_rel',
        column1='plan_user_id',
        column2='team_user_id',
        help="Sale Order and invoices of these users will be added to the achievements of the salesperson",
        domain="[('share', '=', False)]",
        copy=True)

    date_from = fields.Date("From", compute='_compute_date_from', store=True, readonly=False)
    date_to = fields.Date("To")

    other_plans = fields.Many2many('sale.commission.plan', string="Other plans",
                                   help='For reference only. Useful to quickly control the consistency between salespeople.',
                                   compute='_compute_other_plans')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for user in self:
            if user.date_to and user.date_from and user.date_to < user.date_from:
                raise exceptions.UserError(_("The assignment start date must be before the end date"))
            if user.date_from and user.plan_id.date_from and user.date_from < user.plan_id.date_from:
                raise exceptions.UserError(_("The sales person's assignment must be within the commission plan period."))
            if user.date_from and user.plan_id.date_to and user.date_from > user.plan_id.date_to:
                raise exceptions.UserError(_("User period cannot start after the plan."))
            if user.date_to and user.plan_id.date_to and user.date_to > user.plan_id.date_to:
                raise exceptions.UserError(self.env._("User period cannot end after the plan."))
            if user.plan_id.target_type == 'dynamic':
                dynamic_msg = None
                date_from_list = user.plan_id.target_ids.mapped('date_from')
                date_to_list = user.plan_id.target_ids.mapped('date_to')
                if user.date_from and not user.date_from in date_from_list:
                    allowed_date_from = [format_date(self.env, d) for d in date_from_list]
                    current_date_from = format_date(self.env, user.date_from)
                    dynamic_msg = self.env._("The 'From' date value (%(df)s) of the Sales People must correspond to the target periods.\ne.g. %(adf)s", df=current_date_from, adf=", ".join(allowed_date_from))
                if user.date_to and not user.date_to in date_to_list:
                    allowed_date_to = [format_date(self.env, d) for d in date_to_list]
                    current_date_to = format_date(self.env, user.date_to)
                    dynamic_msg = self.env._("The 'To' date value (%(dt)s) of the Sales People must correspond to the target periods.\ne.g. %(adt)s", dt=current_date_to, adt=", ".join(allowed_date_to))
                if dynamic_msg and not self.env.context.get('install_demo'):
                    # exception are not raised during demo data installation. We prefer bad demo data than raising blocking errors.
                    raise exceptions.UserError(dynamic_msg)

    def _compute_display_name(self):
        for record in self:
            record.display_name = _("%(user)s - %(plan)s",
                                    plan=record.plan_id.name,
                                    user=record.user_id.name)

    @api.depends('user_id', 'plan_id.date_from', 'plan_id.date_to', 'date_from', 'date_to')
    def _compute_other_plans(self):
        all_user_lines = self.search([
            ('user_id', 'in', self.user_id.ids),
            ('plan_id.state', 'in', ['draft', 'approved']),
        ])
        lines_by_plan_user = defaultdict(list)
        plan_ids = all_user_lines.plan_id
        for line in all_user_lines:
            lines_by_plan_user[line.plan_id.id, line.user_id.id].append(line)
        for pu in self:
            pu_date_from = pu.date_from or pu.plan_id.date_from
            pu_date_to = pu.date_to or pu.plan_id.date_to
            other_plans_ids = []
            for plan in (plan_ids - pu.plan_id._origin - pu.plan_id):
                user_lines = lines_by_plan_user.get((plan.id, pu.user_id.id))
                if not user_lines:
                    continue
                # get employee-specific dates for this plan
                for user in user_lines:
                    plan_date_from = user.date_from or plan.date_from
                    plan_date_to = user.date_to or plan.date_to
                    if plan_date_to < pu_date_from or plan_date_from > pu_date_to:
                        # no overlap
                        continue
                    other_plans_ids.append(plan.id)
                    break
            pu.other_plans = [Command.clear()] if not other_plans_ids else [Command.set(other_plans_ids)]

    @api.depends('plan_id', 'plan_id.date_from')
    def _compute_date_from(self):
        for user in self:
            if not user.plan_id.date_from:
                continue
            user.date_from = user.plan_id.date_from
