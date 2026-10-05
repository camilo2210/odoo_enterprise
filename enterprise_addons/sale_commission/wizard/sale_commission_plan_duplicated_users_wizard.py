# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import Command, api, models, fields


class SaleCommissionPlanDuplicatedUserWizard(models.TransientModel):
    _name = 'sale.commission.plan.issue.wizard'
    _description = "Wizard for detecting user appearing in multiple sale.commission.plan.user user_ids record"

    plan_ids = fields.Many2many('sale.commission.plan', compute='_compute_plan_ids')
    issue_user_ids = fields.One2many('sale.commission.problematic_user.wizard', 'wizard_id', compute='_compute_user_gap_and_overlap')

    def _compute_plan_ids(self):
        active_id = self.env.context.get('active_id')
        active_ids = self.env.context.get('active_ids')
        plans = self.env['sale.commission.plan'].browse(active_ids or active_id)
        for wizard in self:
            wizard.plan_ids = plans

    def _get_overlap_and_gap(self, plan_ids):
        self.plan_ids.flush_recordset()
        self.plan_ids.user_ids.flush_recordset()
        self.env.cr.execute("""
WITH periods AS (
  SELECT
        scp.id AS plan_id,
        r.plan_user_id,
        r.team_user_id,
        scpu.user_id AS sale_user_id,
        daterange(
            COALESCE(scpu.date_from, scp.date_from),
            COALESCE(scpu.date_to, scp.date_to),
            '[)'
        ) AS period
    FROM com_plan_user_rel r
    JOIN sale_commission_plan_user scpu ON scpu.id = r.plan_user_id
    JOIN sale_commission_plan scp ON scp.id = scpu.plan_id
   WHERE scp.id IN %s
   GROUP BY
        team_user_id,
        plan_user_id,
        scpu.date_from,
        scpu.date_to,
        scpu.user_id,
        scp.date_from,
        scp.date_to,
        scp.id
), ordered AS (
    SELECT
        *,
        isempty(period) as is_empty,
        LOWER(period) AS start_date,
        UPPER(period) AS end_date,
        LEAD(LOWER(period)) OVER (
            PARTITION BY team_user_id
            ORDER BY LOWER(period)
        ) AS next_start,
        LEAD(plan_user_id) OVER (
            PARTITION BY team_user_id
            ORDER BY LOWER(period)
        ) AS next_plan_user_id
    FROM periods
)
SELECT
    plan_user_id,
    next_plan_user_id,
    ordered.plan_id,
    scpu.plan_id AS next_plan_id,
    team_user_id,
    sale_user_id,
    start_date,
    end_date,
    next_start,
    is_empty,
    -- overlap
    CASE
        WHEN next_start < end_date THEN daterange(next_start, end_date, '[)')
        WHEN next_start = end_date THEN daterange(next_start, end_date, '[]')
    END AS overlap_period,

    -- gap
    CASE
        WHEN next_start > end_date + INTERVAL '1 days' THEN daterange(end_date, next_start, '[)')
    END AS gap_period

FROM ordered
LEFT JOIN sale_commission_plan_user scpu ON scpu.id=next_plan_user_id
WHERE next_start IS NOT NULL OR is_empty IS TRUE
        """, [tuple(plan_ids.ids)])
        return self.env.cr.dictfetchall()

    @api.depends('plan_ids')
    def _compute_user_gap_and_overlap(self):
        overlap_and_gap = self._get_overlap_and_gap(self.plan_ids._origin)
        results_by_plan = defaultdict(list)
        for val in overlap_and_gap:
            results_by_plan[val['plan_id']].append(val)
        for wizard in self:
            if wizard.plan_ids:
                values = []
                for plan in wizard.plan_ids:
                    values += results_by_plan.get(plan._origin.id, [])
            else:
                values = overlap_and_gap
            issue_values = []
            for vals in values:
                is_empty = vals['is_empty']
                if is_empty:
                    next_start = vals['next_start']
                    end_date = vals['end_date']
                    if not (next_start and end_date):
                        plan_user = self.env['sale.commission.plan.user'].browse(vals['plan_user_id'])
                        next_start = plan_user.date_from
                        end_date = plan_user.date_to
                    conflicting_plan_id = vals['plan_id']
                else:
                    end_date = vals['end_date']
                    next_start = vals['next_start']
                    conflicting_plan_id = vals['next_plan_id']

                can_compare = end_date and next_start

                if vals['overlap_period'] or (can_compare and end_date == next_start) or is_empty:
                    # overlap can happen when
                    # 1) start_interval == end_interval
                    # 2) start_interval is after end_interval
                    date_from = min(end_date, next_start)
                    date_to = max(end_date, next_start)
                    issue_values += [Command.create({
                        'issue_type': 'overlap',
                        'wizard_id': wizard.id,
                        'plan_id': vals['plan_id'],
                        'conflicting_plan_id': conflicting_plan_id,
                        'sale_user_id': vals['sale_user_id'],
                        'user_id': vals['team_user_id'],
                        'date_from': date_from,
                        'date_to': date_to,
                    })]
                if vals['gap_period']:
                    date_from = min(end_date, next_start)
                    date_to = max(end_date, next_start)
                    issue_values += [Command.create({
                        'issue_type': 'gap',
                        'wizard_id': wizard.id,
                        'plan_id': vals['plan_id'],
                        'conflicting_plan_id': vals['next_plan_id'],
                        'sale_user_id': vals['sale_user_id'],
                        'user_id': vals['team_user_id'],
                        'date_from': date_from,
                        'date_to': date_to,
                    })]
            wizard.issue_user_ids = issue_values


class SaleCommissionPlanDuplicatedUsersIdsWizard(models.TransientModel):
    _name = 'sale.commission.problematic_user.wizard'
    _description = "Overlap/Gap period per plan and user"

    wizard_id = fields.Many2one('sale.commission.plan.issue.wizard', required=True)
    sale_user_id = fields.Many2one('res.users', "Salesperson", required=True, domain="[('share', '=', False)]")
    user_id = fields.Many2one('res.users', "Team Member", required=True, domain="[('share', '=', False)]")
    plan_id = fields.Many2one('sale.commission.plan', required=True)
    conflicting_plan_id = fields.Many2one('sale.commission.plan', required=True)
    date_from = fields.Date("Conflict From", required=True)
    date_to = fields.Date("Conflict To")
    state = fields.Selection(related='plan_id.state')
    issue_type = fields.Selection([('gap', 'Gap'), ('overlap', 'Overlap')], string="Conflict Type")
