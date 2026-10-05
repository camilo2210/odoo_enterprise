# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import SQL


class SaleCommissionAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    @api.model
    def _get_subscription_currency_rates(self):
        """ Get a query to be able to convert the MRR log amount (in SO currency) to the currency of the current company.
        This method uses the same logic than sale.order.log.report.
        """
        company = self.env.company
        conversion_date = fields.Date.context_today(self)
        # In case we want to replay data at previous date
        if self.env.context.get('conversion_date'):
            conversion_date = fields.Date.to_date(self.env.context['conversion_date'])
        return SQL("""
            default_rate AS (
                SELECT
                    %(currency_id)s AS currency_id,
                    %(currency_name)s AS name,
                    %(company_id)s AS company_id,
                    %(conversion_date)s::DATE AS date,
                    1 AS rate
            ),
            sub_rate AS (
                SELECT
                    rc.id AS currency_id,
                    rc.name,
                    rcr.company_id,
                    (array_agg(rcr.name order by rcr.name desc))[1] as date,
                    (array_agg(rcr.rate order by rcr.name desc))[1] as rate
                FROM res_currency rc
                JOIN res_currency_rate rcr
                    ON rcr.currency_id = rc.id
                WHERE rc.active
                   AND rcr.name <= %(conversion_date)s
                GROUP BY rc.id, rc.name, rcr.company_id
            ),
            sub_rate_query AS (
                SELECT *
                FROM sub_rate
                UNION ALL
                SELECT *
                FROM default_rate
                WHERE NOT EXISTS (
                    SELECT 1 FROM sub_rate
                )
            ),
            """,
            conversion_date=conversion_date,
            currency_id=company.currency_id.id,
            currency_name=company.currency_id.name,
            company_id=company.id,
        )

    @api.model
    def _get_filtered_order_log_cte(self, users=None, teams=None):
        date_from, date_to = self._get_achievement_default_dates()
        conditions = []
        if users:
            conditions.append(SQL("l.user_id IN %s", tuple(users.ids)))
        if teams:
            conditions.append(SQL("l.team_id IN %s", tuple(teams.ids)))
        if date_to:
            conditions.append(SQL("l.event_date <= %s", date_to))
        if date_from:
            conditions.append(SQL("l.event_date >= %s", date_from))
        return SQL("""
        filtered_order_logs AS (
            SELECT
                    l.id::bigint,
                    l.order_id,
                    l.plan_id,
                    l.amount_signed,
                    l.team_id,
                    l.company_id,
                    l.user_id,
                    l.currency_id,
                    l.event_date,
                    l.effective_date
              FROM sale_order_log l
             WHERE %s
        ),
        """, SQL("\nAND ").join(conditions) or SQL("1=1"))

    @api.model
    def _get_sale_order_log_rates(self):
        return ['mrr']

    @api.model
    def _get_sale_order_log_product(self):
        # TODO BIG CURRENCY CHANGES 0_0
        return SQL("""
            rules.mrr_rate * log.amount_signed::double precision /  log_rate.rate::double precision
        """)

    @api.model
    def _select_rules(self):
        return SQL("""%s
        ,MAX(scpa.recurring_plan_id) AS recurring_plan_id
        """, super()._select_rules())

    @api.model
    def _join_invoices(self, join_type=None):
        return SQL("""%s
          LEFT JOIN sale_order sub ON sub.id=aml.subscription_id
        """, super()._join_invoices(join_type))

    @api.model
    def _where_invoices(self):
        # When the rules has no recurring plan, all invoices match, otherwise only the plan of the subscription
        return SQL("""%s
          AND ((rules.recurring_plan_id IS NULL) OR (rules.recurring_plan_id=sub.plan_id))
        """, super()._where_invoices())

    def _subscription_lines(self, users=None, teams=None):
        log_rates = self._get_sale_order_log_rates()
        return SQL("""
%(subscription_currency_rates)s
%(filtered_order_log_cte)s
subscription_rules AS (
    SELECT
       (scpa.id::bigint << 20) | scpu.id::bigint as id,
        COALESCE(scpu.date_from, scp.date_from) AS date_from,
        COALESCE(scpu.date_to, scp.date_to) AS date_to,
        scpu.user_id AS user_id,
        scpu.id AS plan_user_id,
        ARRAY_AGG(r.team_user_id) FILTER (WHERE r.team_user_id IS NOT NULL) AS user_ids,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        scpa.recurring_plan_id,
        scp.company_id,
        scp.currency_id AS currency_to,
        scp.user_type::text = 'team'::text AS team_rule,
        %(sale_order_log_rates)s
    FROM sale_commission_plan_achievement scpa
    JOIN sale_commission_plan scp ON scp.id = scpa.plan_id
    JOIN sale_commission_plan_user scpu ON scpa.plan_id = scpu.plan_id
    LEFT JOIN com_plan_user_rel r ON scpu.id = r.plan_user_id
    WHERE scp.state::text IN ('approved'::text, 'done'::text)
      AND scp.active
      %(scpa_type_condition)s
      %(scpu_user_condition)s
 GROUP BY scpa.id,
          scpu.id,
          scpu.date_from,
          scp.date_from,
          scpu.date_to,
          scp.date_to,
          scpu.user_id,
          scp.id,
          scpa.recurring_plan_id,
          scp.company_id,
          scp.currency_id,
          scp.user_type

), subscription_commission_lines_team AS (
    SELECT
        ((max(rules.id::bigint) << 23) | (log.id::bigint << 3) | 0::bigint) *10+5 as id,
        rules.user_id,
        rules.plan_user_id,
        MAX(log.user_id) AS document_user_id,
        MAX(log.team_id) AS team_id,
        rules.plan_id,
        SUM(%(sale_order_log_product)s) AS achieved,
        NULL::numeric AS paid_ratio,
        NULL::text AS payment_state,
        log.currency_id AS currency_id,
        MAX(log.event_date) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(log.company_id) AS achievement_company_id,
        MAX(log.order_id) AS related_res_id,
        MAX(so.name) AS related_res_name,
        MAX(so.partner_id) AS partner_id

    FROM subscription_rules rules
    JOIN filtered_order_logs log ON log.team_id=rules.team_id
    JOIN sale_order so ON so.id = log.order_id
    JOIN sub_rate_query log_rate ON log_rate.currency_id=log.currency_id AND log_rate.company_id=log.company_id
    WHERE rules.team_rule
      AND (rules.recurring_plan_id IS NULL OR log.plan_id = rules.recurring_plan_id)
      AND log.team_id = rules.team_id
      %(log_team_condition)s
      AND log.event_date BETWEEN rules.date_from AND rules.date_to
      AND log.effective_date IS NOT NULL
    GROUP BY
        log.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id,
        log.currency_id
), subscription_commission_lines_user AS (
    SELECT
        ((max(rules.id::bigint) << 23) | (log.id::bigint << 3) | 1::bigint) *10+6 as id,
        rules.user_id,
        rules.plan_user_id,
        MAX(log.user_id) AS document_user_id,
        MAX(log.team_id) AS team_id,
        rules.plan_id,
        SUM(%(sale_order_log_product)s) AS achieved,
        NULL::numeric AS paid_ratio,
        NULL::text AS payment_state,
        log.currency_id AS currency_id,
        MAX(log.event_date) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(log.company_id) AS achievement_company_id,
        MAX(log.order_id) AS related_res_id,
        MAX(so.name) AS related_res_name,
        MAX(so.partner_id) AS partner_id

    FROM subscription_rules rules
        JOIN filtered_order_logs log ON log.user_id=rules.user_id OR log.user_id = ANY(rules.user_ids)
    JOIN sale_order so ON so.id = log.order_id
    JOIN sub_rate_query log_rate ON log_rate.currency_id=log.currency_id AND log_rate.company_id=log.company_id
    WHERE NOT rules.team_rule
      AND (rules.recurring_plan_id IS NULL OR log.plan_id = rules.recurring_plan_id)
      %(log_user_condition)s
      AND log.event_date::DATE BETWEEN rules.date_from::DATE AND rules.date_to::DATE
      AND log.effective_date IS NOT NULL
    GROUP BY
        log.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id,
        log.currency_id
), subscription_commission_lines AS (
    (SELECT *, 'sale.order' AS related_res_model FROM subscription_commission_lines_team)
    UNION ALL
    (SELECT *, 'sale.order' AS related_res_model FROM subscription_commission_lines_user)
        )""",
        subscription_currency_rates=self._get_subscription_currency_rates(),
        filtered_order_log_cte=self._get_filtered_order_log_cte(users=users, teams=teams),
        sale_order_log_rates=self._rate_to_case(log_rates),
        sale_order_log_product=self._get_sale_order_log_product(),
        scpa_type_condition=SQL("AND scpa.type::text IN %s", tuple(log_rates)),
        scpu_user_condition=SQL("AND scpu.user_id in %s", tuple(users.ids)) if users else SQL(),
        log_user_condition=SQL("AND log.user_id in %s", tuple(users.ids)) if users else SQL(),
        log_team_condition=SQL("AND log.team_id in %s", tuple(teams.ids)) if teams else SQL(),
    ), 'subscription_commission_lines'

    def _commission_lines_cte(self, users=None, teams=None):
        return super()._commission_lines_cte(users, teams) + [self._subscription_lines(users, teams)]
