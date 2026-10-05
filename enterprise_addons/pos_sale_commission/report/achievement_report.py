# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.tools import SQL


class SaleCommissionAchievementReport(models.Model):
    _inherit = "sale.commission.achievement.report"

    @api.model
    def _get_filtered_pos_order_cte(self, users=None, teams=None):
        date_from, date_to = self._get_achievement_default_dates()
        conditions = [
            SQL("po.state::text IN ('paid'::text, 'done'::text)"),
        ]
        if teams:
            conditions.append(SQL("po.crm_team_id IN %s", tuple(teams.ids)))
        if date_to:
            conditions.append(SQL("date_order::DATE <= %s", date_to))
        if date_from:
            conditions.append(SQL("date_order::DATE >= %s::timestamp without time zone", date_from))
        # We don't filter by user_id because with user_ids on plan_user, it would prevent some SO to be displayed
        query = SQL("""
        filtered_pos_orders AS (
            SELECT
                    po.id,
                    po.name,
                    po.pos_reference,
                    po.crm_team_id,
                    po.state,
                    po.currency_rate,
                    po.company_id,
                    pc.currency_id,
                    po.user_id,
                    po.date_order,
                    po.partner_id
              FROM pos_order po
              JOIN pos_config pc ON pc.id=po.config_id
             WHERE %s
        )
        """, SQL("\nAND ").join(conditions))
        return query

    @api.model
    def _get_pos_sale_rates(self):
        return ['amount_sold_pos', 'qty_sold_pos']

    @api.model
    def _get_pos_rates_product(self):
        return SQL("""
            rules.amount_sold_pos_rate * pol.price_subtotal::double precision / fpos.currency_rate::double precision +
            rules.qty_sold_pos_rate * pol.qty::double precision
        """)

    @api.model
    def _select_pos(self):
        return SQL("""
          fpos.id AS related_res_id,
          MAX(
            CONCAT(
                fpos.name,
                CASE
                    WHEN fpos.pos_reference IS NOT NULL
                    THEN CONCAT(' (', fpos.pos_reference, ')')
                    ELSE ''
                END
            )
          ) AS related_res_name,
          MAX(fpos.partner_id) AS partner_id
        """)

    @api.model
    def _join_pos(self, join_type=None):
        if join_type == 'team':
            condition = SQL("fpos.crm_team_id = rules.team_id")
        else:
            # JOIN ON USER
            condition = SQL("fpos.user_id = rules.user_id OR fpos.user_id = ANY(rules.user_ids)")
        return SQL("""
        JOIN filtered_pos_orders fpos ON %s
        JOIN pos_order_line pol
          ON pol.order_id = fpos.id
        """, condition)

    @api.model
    def _where_pos(self):
        where = SQL("""
          AND (fpos.date_order BETWEEN rules.date_from AND rules.date_to)
          AND (rules.product_id IS NULL OR rules.product_id = pol.product_id)
          AND (rules.product_categ_id IS NULL OR pt_categ.parent_path LIKE rule_categ.parent_path || '%%')
        """)
        return where

    def _pos_order_lines(self, users=None, teams=None):
        pos_sale_rates = self._get_pos_sale_rates()
        pos_rate_product = self._get_pos_rates_product()
        return SQL("""
%(pos_order_cte)s,
pos_rules AS (
    SELECT
        COALESCE(scpu.date_from, scp.date_from) AS date_from,
        COALESCE(scpu.date_to, scp.date_to) AS date_to,
        scpu.user_id AS user_id,
        scpu.id AS plan_user_id,
        ARRAY_AGG(r.team_user_id) FILTER (WHERE r.team_user_id IS NOT NULL) AS user_ids,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        scpa.product_id,
        scpa.product_categ_id,
        scp.company_id,
        scp.currency_id AS currency_id,
        scp.user_type::text = 'team'::text AS team_rule,
        %(rate_to_case)s
    FROM sale_commission_plan_achievement scpa
    JOIN sale_commission_plan scp ON scp.id = scpa.plan_id
    JOIN sale_commission_plan_user scpu ON scpa.plan_id = scpu.plan_id
    LEFT JOIN com_plan_user_rel r ON scpu.id = r.plan_user_id
    WHERE scp.active
      AND scp.state::text IN ('approved'::text, 'done'::text)
      %(scpa_type_condition)s
      %(scpu_user_condition)s
    GROUP BY scpu.date_from,
             scp.date_from,
             scpu.date_to,
             scp.date_to,
             scpu.user_id,
             scpu.id,
             scp.team_id,
             scp.id,
             scpa.type,
             scpa.rate,
             scpa.product_id,
             scpa.product_categ_id,
             scp.company_id,
             scp.currency_id,
             scp.user_type

), pos_commission_lines_team AS (
    SELECT
        MAX(pol.id)::BIGINT *10 as id,
        rules.user_id,
        rules.plan_user_id AS plan_user_id,
        MAX(fpos.user_id) AS document_user_id,
        MAX(rules.team_id) AS team_id,
        rules.plan_id,
        SUM(%(pos_rate_product)s) AS achieved,
        NULL::numeric AS paid_ratio,
        NULL::text AS payment_state,
        MAX(fpos.currency_id) AS currency_id,
        MAX(fpos.date_order) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(fpos.company_id) AS achievement_company_id,
        %(select_pos)s
    FROM pos_rules rules
    %(join_crm_team)s
    LEFT JOIN product_product pp
      ON pol.product_id = pp.id
    LEFT JOIN product_template pt
      ON pp.product_tmpl_id = pt.id
    LEFT JOIN product_category pt_categ
      ON pt.categ_id = pt_categ.id
    LEFT JOIN product_category rule_categ
      ON rules.product_categ_id = rule_categ.id
    WHERE rules.team_rule
      AND fpos.crm_team_id = rules.team_id
    %(team_condition)s
    %(where_pos)s
    GROUP BY
        fpos.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id
), pos_commission_lines_user  AS (
    SELECT
        MAX(pol.id)::BIGINT *10+9 as id,
        rules.user_id,
        rules.plan_user_id AS plan_user_id,
        MAX(fpos.user_id) AS document_user_id,
        MAX(fpos.crm_team_id) AS team_id,
        rules.plan_id,
        SUM(%(pos_rate_product)s) AS achieved,
        NULL::numeric AS paid_ratio,
        NULL::text AS payment_state,
        MAX(fpos.currency_id) AS currency_id,
        MAX(fpos.date_order) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(fpos.company_id) AS achievement_company_id,
        %(select_pos)s
    FROM pos_rules rules
    %(join_pos_user)s
    LEFT JOIN product_product pp
      ON pol.product_id = pp.id
    LEFT JOIN product_template pt
      ON pp.product_tmpl_id = pt.id
    LEFT JOIN product_category pt_categ
      ON pt.categ_id = pt_categ.id
    LEFT JOIN product_category rule_categ
      ON rules.product_categ_id = rule_categ.id
    WHERE NOT rules.team_rule
        %(user_condition)s
        %(where_pos)s
    GROUP BY
        fpos.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id
), pos_commission_lines AS (
    (SELECT pos_commission_lines_team.id::bigint as id,
            pos_commission_lines_team.user_id,
            pos_commission_lines_team.plan_user_id,
            pos_commission_lines_team.document_user_id,
            pos_commission_lines_team.team_id,
            pos_commission_lines_team.plan_id,
            pos_commission_lines_team.achieved,
            NULL::numeric AS paid_ratio,
            NULL::text AS payment_state,
            pos_commission_lines_team.currency_id,
            pos_commission_lines_team.date,
            pos_commission_lines_team.plan_company_id,
            pos_commission_lines_team.achievement_company_id,
            pos_commission_lines_team.related_res_id,
            pos_commission_lines_team.related_res_name,
            pos_commission_lines_team.partner_id,
           'pos.order' AS related_res_model
       FROM pos_commission_lines_team)
    UNION ALL
    (SELECT pos_commission_lines_user.id::bigint as id,
            pos_commission_lines_user.user_id,
            pos_commission_lines_user.plan_user_id,
            pos_commission_lines_user.document_user_id,
            pos_commission_lines_user.team_id,
            pos_commission_lines_user.plan_id,
            pos_commission_lines_user.achieved,
            NULL::numeric AS paid_ratio,
            NULL::text AS payment_state,
            pos_commission_lines_user.currency_id,
            pos_commission_lines_user.date,
            pos_commission_lines_user.plan_company_id,
            pos_commission_lines_user.achievement_company_id,
            pos_commission_lines_user.related_res_id,
            pos_commission_lines_user.related_res_name,
            pos_commission_lines_user.partner_id,
            'pos.order' AS related_res_model
       FROM pos_commission_lines_user)
    )""",
    pos_order_cte=self._get_filtered_pos_order_cte(users=users, teams=teams),
    rate_to_case=self._rate_to_case(pos_sale_rates),
    scpa_type_condition=SQL("AND scpa.type IN %s", tuple(pos_sale_rates)),
    scpu_user_condition=SQL("AND scpu.user_id in %s", tuple(users.ids)) if users else SQL(),
    pos_rate_product=pos_rate_product,
    select_pos=self._select_pos(),
    join_crm_team=self._join_pos(join_type='team'),
    team_condition=SQL("AND fpos.crm_team_id in %s", tuple(teams.ids)) if teams else SQL(),
    where_pos=self._where_pos(),
    join_pos_user=self._join_pos(join_type='user'),
    user_condition=SQL("AND fpos.user_id in %s", tuple(users.ids)) if users else SQL(),
    ), 'pos_commission_lines'

    def _commission_lines_cte(self, users=None, teams=None):
        return super()._commission_lines_cte(users, teams) + [self._pos_order_lines(users, teams)]
