# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime

from odoo import models, api, fields
from odoo.tools import SQL

from odoo.addons.account.models.account_move import PAYMENT_STATE_SELECTION
from odoo.addons.resource.models.utils import filter_map_domain

class SaleCommissionAchievementReport(models.Model):
    _name = 'sale.commission.achievement.report'
    _description = "Sales Achievement Report"
    _order = 'id'
    _auto = False

    id_str = fields.Char(readonly=True)
    target_id = fields.Many2one('sale.commission.plan.target', "Period", readonly=True)
    plan_id = fields.Many2one('sale.commission.plan', "Commission Plan", readonly=True)
    state = fields.Selection(related='plan_id.state')
    user_id = fields.Many2one('res.users', "Sales Person", readonly=True)
    document_user_id = fields.Many2one('res.users', "User", readonly=True, help="Person assigned to the source document")
    team_id = fields.Many2one('crm.team', "Sales Team", readonly=True)
    achieved = fields.Monetary("Achieved", readonly=True, currency_field='currency_id')

    target_amount = fields.Monetary(readonly=True, currency_field='currency_id', aggregator='avg')
    commission_target_amount = fields.Monetary(readonly=True, currency_field='currency_id', aggregator='avg',
                                               help="Sum of target amount per plan paid on the same date")
    target_rate = fields.Float("Achieved Rate", readonly=True, aggregator=None,
                               help="Achieved over the target of that period, meaningless in group by")
    commission_rate = fields.Float("Commission Rate", readonly=True, aggregator=None,
                                   help="Achieved over the commission target amount")
    currency_id = fields.Many2one('res.currency', "Currency", readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    date = fields.Date(string="Date", readonly=True)
    partner_id = fields.Many2one('res.partner', "Customer", readonly=True)

    related_res_model = fields.Char(readonly=True)
    related_res_id = fields.Many2oneReference("Related", model_field='related_res_model', readonly=True)
    related_res_name = fields.Char('Related Document')

    #  Invoicing columns
    payment_state = fields.Selection(selection=PAYMENT_STATE_SELECTION, readonly=True)
    paid_ratio = fields.Float(readonly=True, aggregator=None)

    ################################################################################
    # Readonly Cursor hacks
    # These methods use a readonly cursor everywhere else in odoo but here we need a RW cursor because
    # we are creating a view (necessary even if the view is not materialized).

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit)
    # Make sure the method is never readonly in this model
    web_search_read._readonly = False

    @api.readonly
    def web_read(self, specification: dict[str, dict]) -> list[dict]:
        values_list = super().web_read(specification)
        for values in values_list:
            if values.get('id_str'):
                values['id'] = values['id_str']
        return values_list

    @api.model
    def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
        return super().formatted_read_group(domain, groupby, aggregates, having, offset, limit, order)
    formatted_read_group._readonly = False

    @api.model
    def formatted_read_grouping_sets(self, domain, grouping_sets, aggregates=(), *, order=None):
        # In the pivot view, we don't want the hierarchical naming of department_id (hr.department)
        return super().formatted_read_grouping_sets(
            domain, grouping_sets, aggregates, order=order,
        )
    formatted_read_grouping_sets._readonly = False

    ################################################################################

    @api.model
    def _search(self, domain, *args, **kwargs):
        """ Extract the currency conversion date form the date_to field.
        It is used to be able to get fixed results not depending on the currency daily rates.
        The date is converted to a string to allow updating the date value in view customizations.
        """
        # We want all "date_to" fields except for the one on plan_id
        def _map_condition(condition):
            field_expr = condition.field_expr
            if 'date_to' in field_expr and field_expr != 'plan_id.date_to':
                return condition
            return None

        model = self
        date_to_domain = domain and filter_map_domain(domain, _map_condition)
        date_to_domain = date_to_domain and date_to_domain.optimize_full(model)
        date_to_list = date_to_domain and [cond.value for cond in date_to_domain.iter_conditions() if isinstance(cond.value, date)]
        if date_to_list and not 'conversion_date' in self.env.context:
            conversion_date = max(date_to_list)
            model = model.with_context(conversion_date=conversion_date.strftime('%Y-%m-%d'))
        return super(SaleCommissionAchievementReport, model)._search(domain, *args, **kwargs)

    def open_related(self):
        self.ensure_one()
        # web_read exposes id_str as the client-side ID to preserve bigint precision.
        achievement = self.browse(int(self.id))
        return {
            'view_mode': 'form',
            'res_model': achievement.related_res_model,
            'res_id': achievement.related_res_id,
            'type': 'ir.actions.act_window',
        }

    @api.model
    def _get_currency_rate(self):
        companies = self.env['res.company'].search([], order='id asc')
        current_company = self.env.company
        conversion_date = fields.Date.context_today(self)
        if self.env.context.get('conversion_date'):
            conversion_date = datetime.strptime(self.env.context['conversion_date'], '%Y-%m-%d')
        currency_rate = [(current_company.id, current_company.currency_id.id, conversion_date.strftime('%Y-%m-%d'), 1)]
        for comp in companies - current_company:
            rate = comp.currency_id._convert(from_amount=1, to_currency=current_company.currency_id, company=current_company, date=conversion_date, round=False)
            currency_rate.append((comp.id, comp.currency_id.id, conversion_date.strftime('%Y-%m-%d'), rate))
        return SQL("""currency_rate AS (
            SELECT * FROM UNNEST(%s, %s, %s, %s) AS currency_values(company_id, currency_id, conversion_date, rate)
        )""", *map(list, zip(*currency_rate)))

    @api.model
    def _get_target_query(self):
        return SQL("""
        all_converted_target AS (
            SELECT t.id,
                   t.date_from,
                   t.date_to,
                   t.amount * cr.rate AS amount,
                   t.payment_amount * cr.rate AS payment_amount,
                   t.payment_date,
                   scp.company_id,
                   scp.id AS plan_id,
                   cr.rate
            FROM sale_commission_plan_target t
            JOIN sale_commission_plan scp ON scp.id=t.plan_id
            LEFT JOIN currency_rate cr ON scp.company_id = cr.company_id
            WHERE scp.active
              AND scp.state='approved'
        ),
        allowed_plans AS (
            SELECT scp.id scp_id,
                   array_agg(other_plan.id) o_ids
              FROM sale_commission_plan scp
              JOIN com_dynamic_plan_rel dpr ON dpr.dynamic_plan_id=scp.id
              JOIN sale_commission_plan other_plan ON other_plan.id=dpr.other_user_plan_id
             WHERE scp.target_type='dynamic'
               AND scp.active
               AND scp.state='approved'
               AND other_plan.active AND other_plan.state='approved'
          GROUP BY scp.id
        ), target_team AS (
            SELECT array_agg(t.id) AS target_ids,
                   t.date_from,
                   t.date_to,
                   SUM(t.amount) AS amount,
                   SUM(t.payment_amount) AS payment_amount,
                   scp.currency_id,
                   ARRAY_AGG(scp.id) AS plan_ids,
                   r.plan_user_id,
                   dynamic_user.plan_id AS dynamic_plan_id,
                   ARRAY_AGG(r.team_user_id) AS team_user_id,
                   ap.o_ids
              FROM sale_commission_plan_user scpu
              JOIN sale_commission_plan scp on scp.id = scpu.plan_id
              JOIN com_plan_user_rel r ON r.team_user_id=scpu.user_id
              JOIN sale_commission_plan_user dynamic_user ON dynamic_user.id=r.plan_user_id
              JOIN allowed_plans ap ON ap.scp_id=dynamic_user.plan_id
              JOIN all_converted_target t on t.plan_id=scp.id AND t.plan_id=ANY(ap.o_ids)
             WHERE scp.state='approved'
               AND scp.active
          GROUP BY t.date_from,
                   t.date_to,
                   scp.currency_id,
                   r.plan_user_id,
                   dynamic_user.plan_id,
                   ap.o_ids
        ), user_data as (
            SELECT
                    era.id AS target_id,
                    era.date_from,
                    era.date_to,
                    era.plan_id AS plan_id,
                    MAX(scpu.id) as plan_user_id,
                    MAX(scpu.user_id) AS user_id,
                    MAX(scp.company_id) AS company_id,
                    -- these amounts are already converted in all_converted_target
                    CASE
                        WHEN scp.target_type='static' THEN MAX(era.amount)
                        ELSE SUM(tt.amount)
                    END AS amount,
                    CASE
                        WHEN scp.target_type='static' THEN MAX(era.payment_amount)
                        ELSE SUM(tt.payment_amount)
                    END AS payment_amount,
                    MAX(era.payment_date) AS payment_date

            FROM all_converted_target era
            LEFT JOIN sale_commission_plan_user scpu
                ON scpu.plan_id=era.plan_id
                AND COALESCE(scpu.date_from, era.date_from)<era.date_to
                AND COALESCE(scpu.date_to, era.date_to)>era.date_from
            JOIN sale_commission_plan scp ON scp.id = scpu.plan_id
            LEFT JOIN target_team tt ON tt.plan_user_id = scpu.id AND tt.date_from=era.date_from AND tt.date_to=era.date_to
            GROUP BY
                    era.id,
                    era.date_from,
                    era.date_to,
                    era.plan_id,
                    scpu.user_id,
                    scp.company_id,
                    scp.target_type
        ), targets AS (
            SELECT
                    era.target_id AS id,
                    era.plan_id AS plan_id,
                    era.plan_user_id,
                    MAX(scp.company_id) AS company_id,
                    MAX(era.amount) AS amount,
                    MAX(era.payment_amount) AS payment_amount,
                    MAX(era.payment_date) AS payment_date,
                    era.date_from,
                    era.date_to

            FROM user_data era
            JOIN sale_commission_plan scp ON scp.id = era.plan_id AND scp.active
            GROUP BY
                    era.target_id,
                    era.plan_id,
                    era.plan_user_id,
                    era.date_from,
                    era.date_to,
                    scp.company_id
        )
        """)

    @api.model
    def _get_achievement_default_dates(self):
        """Return default date_from, date_to and company sql condition for the achievements filtered results
        """
        if self.env.context.get('active_plan_ids'):
            plan_ids = self.env['sale.commission.plan'].sudo().browse(self.env.context['active_plan_ids'])
            date_from = plan_ids and min(plan_ids.mapped('date_from'))
            date_to = plan_ids and max(plan_ids.mapped('date_to'))
        else:
            all_plan_ids = self.env['sale.commission.plan'].sudo().search([('state', 'in', ['approved', 'done'])])
            date_from = all_plan_ids and min(all_plan_ids.mapped('date_from'))
            date_to = all_plan_ids and max(all_plan_ids.mapped('date_to'))
        return date_from, date_to

    @property
    def _table_sql(self):
        users = self.env.context.get('commission_user_ids', [])
        if users:
            users = self.env['res.users'].browse(users).exists()
        teams = self.env.context.get('commission_team_ids', [])
        if teams:
            teams = self.env['crm.team'].browse(teams).exists()
        date_from, date_to = self.env['sale.commission.achievement.report']._get_achievement_default_dates()
        achievement_view = self._get_report_view(users=users, teams=teams)
        if not self._is_materialized_view() and achievement_view:
            self.env.execute_query(achievement_view)

        conditions = []
        if date_to:
            conditions.append(SQL("date <= %s", date_to or fields.date.context_today(self)))
        if users:
            conditions.append(SQL("cl.user_id IN %s", tuple(users.ids)))
        if teams:
            conditions.append(SQL("team_id IN %s", tuple(teams.ids)))
        if date_from:
            conditions.append(SQL("date >= %s", date_from))
        return SQL("""(
        WITH %(currency_rate)s,
        %(target_query)s
        SELECT cl.id,
               cl.id::TEXT as id_str,
               cl.target_id,
               cl.user_id,
               cl.document_user_id,
               cl.team_id,
               cl.achieved * cr.rate AS achieved,
               cl.paid_ratio,
               cl.payment_state,
               %(company_currency_id)s AS currency_id,
               cl.plan_company_id as company_id,
               cl.achievement_company_id as achievement_company_id,
               cl.plan_id,
               cl.related_res_model,
               cl.related_res_id,
               cl.related_res_name,
               cl.date,
               cl.partner_id,
               era.amount AS target_amount,
               era.payment_amount AS commission_target_amount,
               CASE
                   WHEN era.amount IS NULL OR era.amount = 0 THEN 0
                   ELSE cl.achieved / (era.amount)
               END as target_rate,
               CASE
                   WHEN era.payment_amount IS NULL OR era.payment_amount = 0 THEN 0
                   ELSE cl.achieved / (era.payment_amount)
               END as commission_rate
          FROM sale_commission_achievement_report_view cl
          JOIN targets era ON era.id = cl.target_id AND era.plan_user_id=cl.plan_user_id
         JOIN currency_rate cr ON cr.company_id = cl.achievement_company_id
        WHERE %(conditions)s
        )
            """,
            currency_rate=self._get_currency_rate(),
            target_query=self._get_target_query(),
            company_currency_id=self.env.company.currency_id.id,
            conditions=SQL("\nAND ").join(conditions) or SQL("1=1"),
        )

    # ==== Materialized Achievement Generation Methods ====

    def _get_view_parameters(self):
        return SQL("TEMPORARY")

    def _view_post_creation(self):
        return SQL()

    def _is_materialized_view(self):
        return False

    def _get_report_view(self, users=None, teams=None):
        # test the existance of the view. _get_report_view can be called twice in a single transaction by get_views and web_search_read for example.
        # To avoid `psycopg2.errors.DuplicateTable: relation already exists` errors, we only create the view on the first call.
        # Unfortunately tools.sql.table_exists can't be used here because the view is created in a temporary schema
        self.env.cr.execute("""
            SELECT 1 FROM pg_catalog.pg_class AS c
                WHERE c.relname = 'sale_commission_achievement_report_view'
                AND c.relkind = 'v'::"char"
                AND pg_catalog.pg_table_is_visible(c.oid)
        """)
        res = self.env.cr.fetchone()
        if res:
            # The view is already defined in this transaction
            return None
        return SQL("""
            CREATE %(view_parameters)s VIEW sale_commission_achievement_report_view AS
              WITH %(commission_lines)s
            SELECT
                    cl.id,
                    era.id AS target_id,
                    cl.user_id AS user_id,
                    cl.plan_user_id AS plan_user_id,
                    cl.document_user_id AS document_user_id,
                    cl.team_id AS team_id,
                    cl.achieved AS achieved,
                    cl.paid_ratio,
                    cl.payment_state,
                    cl.currency_id AS currency_id,
                    -- company_id is the company of the achivement, used for currency conversion
                    cl.plan_company_id AS plan_company_id,
                    cl.achievement_company_id as achievement_company_id,
                    cl.plan_id,
                    cl.related_res_model,
                    cl.related_res_id::INTEGER AS related_res_id,
                    cl.related_res_name,
                    cl.date::date AS date,
                    cl.partner_id::INTEGER AS partner_id
              FROM commission_lines cl
              JOIN sale_commission_plan_target era
                ON cl.plan_id = era.plan_id
               AND cl.date::date >= era.date_from
               AND cl.date::date <= era.date_to;
               %(post)s
            """,
            view_parameters=self._get_view_parameters(),
            commission_lines=self._commission_lines_query(users=users, teams=teams),
            post=self._view_post_creation(),
        )

    # ==== Query Helpers ====

    @api.model
    def _rate_to_case(self, rates):
        return SQL(",\n").join(
            SQL("CASE WHEN scpa.type::text = %s::text THEN rate ELSE 0::double precision END AS %s", s, SQL.identifier(s + '_rate'))
            for s in rates
        )

    @api.model
    def _get_sale_rates(self):
        return ['amount_sold', 'qty_sold']

    @api.model
    def _get_invoices_rates(self):
        return ['amount_invoiced', 'qty_invoiced', 'amount_paid']

    @api.model
    def _get_sale_rates_product(self):
        return SQL("""
            rules.amount_sold_rate * sol.price_subtotal::double precision / fo.currency_rate::double precision +
            rules.qty_sold_rate * sol.product_uom_qty::double precision
        """)

    @api.model
    def _get_filtered_orders_cte(self, users=None, teams=None):
        date_from, date_to = self._get_achievement_default_dates()
        conditions = [
            SQL("sale_order.state::text = 'sale'::text"),
        ]
        if teams:
            conditions.append(SQL("team_id IN %s", tuple(teams.ids)))
        if date_to:
            conditions.append(SQL("date_order <= %s", date_to))
        if date_from:
            conditions.append(SQL("date_order >= %s::timestamp without time zone", date_from))
        # We don't filter by user_id because with user_ids on plan_user, it would prevent some SO to be displayed
        return SQL("""
        filtered_orders AS (
            SELECT
                    sale_order.id,
                    sale_order.name,
                    sale_order.client_order_ref,
                    sale_order.team_id,
                    sale_order.state,
                    sale_order.currency_rate,
                    sale_order.company_id,
                    sale_order.currency_id,
                    sale_order.user_id,
                    sale_order.date_order,
                    sale_order.partner_id
              FROM sale_order
             WHERE %s
        )
        """, SQL("\nAND ").join(conditions))

    @api.model
    def _get_filtered_moves_cte(self, users=None, teams=None):
        date_from, date_to = self._get_achievement_default_dates()
        conditions = [SQL("date <= %s", date_to or fields.Date.context_today(self))]
        if teams:
            conditions.append(SQL("team_id IN %s", tuple(teams.ids)))
        if date_to:
            conditions.append(SQL("date <= %s", date_to))
        if date_from:
            conditions.append(SQL("date >= %s", date_from))
        # We don't filter by user_id because with user_ids on plan_user, it would prevent some invoices to be displayed
        return SQL("""
        filtered_moves AS (
            SELECT
                    account_move.id::bigint,
                    account_move.name,
                    account_move.team_id,
                    account_move.move_type,
                    account_move.state,
                    account_move.invoice_currency_rate,
                    account_move.company_id,
                    account_move.currency_id,
                    account_move.invoice_user_id,
                    (account_move.amount_total - account_move.amount_residual)/ NULLIF(account_move.amount_total, 0) AS paid_ratio,
                    account_move.payment_state,
                    account_move.date,
                    account_move.partner_id
              FROM account_move
             WHERE account_move.move_type IN ('out_invoice', 'out_refund')
               AND state = 'posted'
               AND %s
        )
        """, SQL("\nAND ").join(conditions) or SQL("1=1"))

    @api.model
    def _get_invoice_rates_product(self):
        amount_invoiced_query = SQL("COALESCE(rules.amount_invoiced_rate * aml.price_subtotal / fm.invoice_currency_rate, 0)")
        qty_invoiced_query = SQL("COALESCE(rules.qty_invoiced_rate * aml.quantity, 0)")
        amount_paid_query = SQL("COALESCE(fm.paid_ratio * rules.amount_paid_rate * aml.price_subtotal / fm.invoice_currency_rate, 0)")
        all_rates_queries = SQL(" + ").join((amount_invoiced_query, qty_invoiced_query, amount_paid_query))
        return SQL("""
        CASE
            WHEN fm.move_type = 'out_invoice' THEN
                %(all_rates_queries)s
            WHEN fm.move_type = 'out_refund' THEN
                (%(all_rates_queries)s) * -1
        END
        """, all_rates_queries=all_rates_queries)

    @api.model
    def _select_invoices(self):
        return SQL("""
          rules.user_id AS user_id, -- rule user to work with team commission
          rules.plan_user_id,
          MAX(fm.invoice_user_id) AS document_user_id,
          MAX(fm.team_id) AS team_id,
          rules.plan_id,
          SUM(%s) AS achieved,
          MAX(fm.paid_ratio) AS paid_ratio,
          MAX(fm.payment_state) AS payment_state,
          MAX(fm.currency_id) AS currency_id,
          -- afr.write_date is the reconcilation date ~ payment date
          CASE
            WHEN MAX(rules.achievement_type) = 'amount_paid' THEN MAX(afr.write_date)
            ELSE MAX(fm.date)
          END AS date,
          MAX(rules.company_id) AS plan_company_id,
          MAX(fm.company_id) AS achievement_company_id,
          fm.id AS related_res_id,
          MAX(
            CONCAT(
                fm.name,
                CASE
                    WHEN aml.ref IS NOT NULL
                    THEN CONCAT(' (', aml.ref, ')')
                    ELSE ''
                END
            )
          ) AS related_res_name,
          MAX(fm.partner_id) AS partner_id
        """, self._get_invoice_rates_product())

    @api.model
    def _join_invoices(self, join_type=None):
        if join_type == 'team':
            condition = SQL("fm.team_id = rules.team_id")
        else:
            # JOIN ON USER
            condition = SQL("fm.invoice_user_id = rules.user_id OR fm.invoice_user_id = ANY(rules.user_ids)")
        return SQL("""
          JOIN filtered_moves fm ON %s
          JOIN account_move_line aml
            ON aml.move_id = fm.id
          JOIN account_move_line pay_line
            ON pay_line.move_id = fm.id AND pay_line.display_type = 'payment_term'::TEXT
          LEFT JOIN account_full_reconcile afr ON afr.id = pay_line.full_reconcile_id
          LEFT JOIN product_product pp
            ON aml.product_id = pp.id
          LEFT JOIN product_template pt
            ON pp.product_tmpl_id = pt.id
        """, condition)

    @api.model
    def _where_invoices(self):
        return SQL("""
          aml.display_type = 'product'
          AND fm.move_type in ('out_invoice', 'out_refund')
          AND fm.state = 'posted'
        """)

    @api.model
    def _select_rules(self):
        return SQL()

    @api.model
    def _select_sales(self):
        return SQL("""
          fo.id AS related_res_id,
          MAX(
            CONCAT(
                fo.name,
                CASE
                    WHEN fo.client_order_ref IS NOT NULL
                    THEN CONCAT(' (', fo.client_order_ref, ')')
                    ELSE ''
                END
            )
          ) AS related_res_name,
          MAX(fo.partner_id) AS partner_id
        """)

    @api.model
    def _join_sales(self, join_type=None):
        if join_type == 'team':
            condition = SQL("fo.team_id = rules.team_id")
        else:
            # JOIN ON USER
            condition = SQL("fo.user_id = rules.user_id OR fo.user_id = ANY(rules.user_ids)")
        return SQL("""
        JOIN filtered_orders fo ON %s
        JOIN sale_order_line sol
          ON sol.order_id = fo.id
        """, condition)

    @api.model
    def _where_sales(self):
        return SQL("""
          AND sol.display_type IS NULL
          AND (fo.date_order BETWEEN rules.date_from AND rules.date_to)
          AND fo.state::TEXT = 'sale'::TEXT
          AND (rules.product_id IS NULL OR rules.product_id = sol.product_id)
          AND (rules.product_categ_id IS NULL OR pt_categ.parent_path LIKE rule_categ.parent_path || '%%')
          AND COALESCE(sol.is_expense, false) = false
          AND COALESCE(sol.is_downpayment, false) = false
        """)

    @api.model
    def _get_filtered_achivement_cte(self, users=None, teams=None):
        date_from = None
        date_to = None
        if self.env.context.get('active_target_ids'):
            target_ids = self.env['sale.commission.plan.target'].sudo().browse(self.env.context['active_target_ids'])
            date_from = min(target_ids.mapped('date_from'))
            date_to = max(target_ids.mapped('date_to'))

        elif self.env.context.get('active_plan_ids'):
            plan_ids = self.env['sale.commission.plan'].sudo().browse(self.env.context['active_plan_ids'])
            date_from = min(plan_ids.mapped('date_from'))
            date_to = max(plan_ids.mapped('date_to'))
        conditions = []
        if date_from:
            conditions.append(SQL("date >= %s", date_from))
        if date_to:
            conditions.append(SQL("date <= %s", date_to))
        return SQL("""
        filtered_adjustments AS (
            SELECT
                    a.id,
                    a.add_user_id,
                    a.add_plan_id,
                    a.reduce_user_id,
                    a.reduce_plan_id,
                    a.company_id,
                    a.currency_id,
                    a.currency_rate,
                    a.achieved,
                    a.date
              FROM sale_commission_achievement a
              WHERE %s
        )
        """, SQL("\nAND ").join(conditions) or SQL("1=1"))

    def _achievement_lines_add(self, users=None, teams=None):
        # Adjustement added to a salesperson
        return SQL("""%s,
achievement_commission_lines_add AS (
    SELECT
        fa.id::bigint *10+7 as id,
        scpu.user_id AS user_id,
        scpu.id AS plan_user_id,
        NULL::INTEGER AS document_user_id,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        fa.achieved::double precision / fa.currency_rate AS achieved,
        NULL::numeric AS paid_ratio,
        NULL::text AS payment_state,
        fa.currency_id AS currency_id,
        fa.date AS date,
        scp.company_id AS plan_company_id,
        scp.company_id AS achievement_company_id,
        fa.id AS related_res_id,
        -- achievement don't involve a customer and record name; needed to match UNION structure with other sources
        NULL::text AS related_res_name,
        NULL::integer AS partner_id,
        'sale.commission.achievement'::text AS related_res_model
    FROM filtered_adjustments fa
    JOIN sale_commission_plan scp ON scp.id = fa.add_plan_id
    JOIN sale_commission_plan_user scpu ON scpu.plan_id = scp.id AND scpu.user_id = fa.add_user_id AND fa.date BETWEEN COALESCE(scpu.date_from,scp.date_from) AND COALESCE(scpu.date_to,scp.date_to)

    WHERE scp.active
      AND scp.state::text IN ('approved'::text, 'done'::text)
      %s
)
        """,
        self._get_filtered_achivement_cte(users=users, teams=teams),
        SQL('AND scpu.user_id in %s', tuple(users.ids)) if users else SQL(),
        ), "achievement_commission_lines_add"

    def _achievement_lines_rem(self, users=None, teams=None):
        # Adjustement removed to a salesperson
        return SQL("""
achievement_commission_lines_rem AS (
    SELECT
        fa.id::bigint *10+8 as id,
        scpu.user_id AS user_id,
        scpu.id AS plan_user_id,
        NULL::INTEGER AS document_user_id,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        (- fa.achieved)::double precision / fa.currency_rate AS achieved,
        NULL::numeric AS paid_ratio,
        NULL::text AS payment_state,
        fa.currency_id AS currency_id,
        fa.date AS date,
        scp.company_id AS plan_company_id,
        scp.company_id AS achievement_company_id,
        fa.id AS related_res_id,
        -- achievement don't involve a customer and record name; needed to match UNION structure with other sources
        NULL::text AS related_res_name,
        NULL::integer AS partner_id,
        'sale.commission.achievement'::text AS related_res_model
    FROM filtered_adjustments fa
    JOIN sale_commission_plan scp ON scp.id = fa.reduce_plan_id
JOIN sale_commission_plan_user scpu ON scpu.plan_id = scp.id AND scpu.user_id = fa.reduce_user_id AND fa.date BETWEEN COALESCE(scpu.date_from,scp.date_from) AND COALESCE(scpu.date_to,scp.date_to)
    WHERE scp.active
      AND scp.state::text IN ('approved'::text, 'done'::text)
      %s
)
""", SQL("AND scpu.user_id IN %s", tuple(users.ids)) if users else SQL()), "achievement_commission_lines_rem"

    def _invoices_lines(self, users=None, teams=None):
        invoice_rates = self._get_invoices_rates()
        return SQL("""
%(filtered_moves_cte)s,
invoices_rules AS (
    SELECT
        scpa.id::bigint,
        COALESCE(scpu.date_from, scp.date_from) AS date_from,
        COALESCE(scpu.date_to, scp.date_to) AS date_to,
        scpu.user_id AS user_id,
        scpu.id AS plan_user_id,
        ARRAY_AGG(r.team_user_id) FILTER (WHERE r.team_user_id IS NOT NULL) AS user_ids,
        scp.team_id AS team_id,
        scp.id AS plan_id,
        scpa.product_id,
        scpa.product_categ_id,
        scpa.type AS achievement_type,
        scp.company_id,
        scp.currency_id AS currency_id,
        scp.user_type::text = 'team'::text AS team_rule,
        %(rate_to_case)s
        %(select_rules)s
    FROM sale_commission_plan_achievement scpa
    JOIN sale_commission_plan scp ON scp.id = scpa.plan_id
    JOIN sale_commission_plan_user scpu ON scpa.plan_id = scpu.plan_id
    LEFT JOIN com_plan_user_rel r ON scpu.id = r.plan_user_id
    WHERE scp.active
      AND scp.state::text IN ('approved'::text, 'done'::text)
      %(scpa_type_condition)s
      %(scpu_user_condition)s
    GROUP BY scp.id,
             scpa.id,
             scpa.type,
             scpa.product_id,
             scpa.product_categ_id,
             scp.company_id,
             scpu.user_id,
             scpu.id,
             scp.user_type,
             scpa.type,
             scpa.rate,
             scp.team_id,
             scpu.date_from,
             scp.date_from,
             scpu.date_to,
             scp.date_to
),
invoice_commission_lines_team AS (
    SELECT
       (MAX(aml.id)::bigint <<20) | max(rules.id)::bigint <<10 | rules.user_id as id,
       %(select_invoices)s
    FROM invoices_rules rules
        %(join_invoices_team)s
    LEFT JOIN product_category pt_categ ON pt.categ_id = pt_categ.id
    LEFT JOIN product_category rule_categ ON rules.product_categ_id = rule_categ.id
    WHERE %(where_invoices)s
      AND rules.team_rule
      AND fm.team_id = rules.team_id
      %(fm_team_condition)s
      AND fm.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR pt_categ.parent_path LIKE rule_categ.parent_path || '%%')
    GROUP BY
        fm.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id,
        fm.invoice_user_id
), invoice_commission_lines_user AS (
    SELECT
       -- row_number is needed here because we have 3 integer (32 bits) to use to create a unique 64 bits integer --> not possible
       row_number() over(order by fm.id, rules.plan_id, rules.user_id) as id,
       %(select_invoices)s
    FROM invoices_rules rules
         %(join_invoices_user)s
    LEFT JOIN product_category pt_categ ON pt.categ_id = pt_categ.id
    LEFT JOIN product_category rule_categ ON rules.product_categ_id = rule_categ.id
    WHERE %(where_invoices)s
      AND NOT rules.team_rule
      AND fm.date BETWEEN rules.date_from AND rules.date_to
      AND (rules.product_id IS NULL OR rules.product_id = aml.product_id)
      AND (rules.product_categ_id IS NULL OR pt_categ.parent_path LIKE rule_categ.parent_path || '%%')
    GROUP BY
        fm.id,
        fm.currency_id,
        fm.date,
        fm.company_id,
        fm.partner_id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id,
        fm.invoice_user_id
), invoice_commission_lines AS (
    (
        SELECT invoice_commission_lines_team.id*10+1 as id,
               invoice_commission_lines_team.user_id,
               invoice_commission_lines_team.plan_user_id,
               invoice_commission_lines_team.document_user_id,
               invoice_commission_lines_team.team_id,
               invoice_commission_lines_team.plan_id,
               invoice_commission_lines_team.achieved,
               invoice_commission_lines_team.paid_ratio AS paid_ratio,
               invoice_commission_lines_team.payment_state,
               invoice_commission_lines_team.currency_id,
               invoice_commission_lines_team.date,
               invoice_commission_lines_team.plan_company_id,
               invoice_commission_lines_team.achievement_company_id,
               invoice_commission_lines_team.related_res_id,
               invoice_commission_lines_team.related_res_name,
               invoice_commission_lines_team.partner_id,
               'account.move' AS related_res_model
          FROM invoice_commission_lines_team
    )
    UNION ALL
    (
        SELECT invoice_commission_lines_user.id*10+2 as id,
               invoice_commission_lines_user.user_id,
               invoice_commission_lines_user.plan_user_id,
               invoice_commission_lines_user.document_user_id,
               invoice_commission_lines_user.team_id,
               invoice_commission_lines_user.plan_id,
               invoice_commission_lines_user.achieved,
               invoice_commission_lines_user.paid_ratio AS paid_ratio,
               invoice_commission_lines_user.payment_state,
               invoice_commission_lines_user.currency_id,
               invoice_commission_lines_user.date,
               invoice_commission_lines_user.plan_company_id,
               invoice_commission_lines_user.achievement_company_id,
               invoice_commission_lines_user.related_res_id,
               invoice_commission_lines_user.related_res_name,
               invoice_commission_lines_user.partner_id,
               'account.move' AS related_res_model
          FROM invoice_commission_lines_user
    )
        )""",
        filtered_moves_cte=self._get_filtered_moves_cte(users=users, teams=teams),
        rate_to_case=self._rate_to_case(invoice_rates),
        select_rules=self._select_rules(),
        scpa_type_condition=SQL("AND scpa.type::text IN %s", tuple(invoice_rates)),
        scpu_user_condition=SQL("AND scpu.user_id IN %s", tuple(users.ids)) if users else SQL(),
        select_invoices=self._select_invoices(),
        join_invoices_team=self._join_invoices(join_type='team'),
        join_invoices_user=self._join_invoices(join_type='user'),
        where_invoices=self._where_invoices(),
        fm_team_condition=SQL("AND fm.team_id IN %s", tuple(teams.ids)) if teams else SQL(),
    ), 'invoice_commission_lines'

    def _sale_lines(self, users=None, teams=None):
        sale_rates = self._get_sale_rates()
        return SQL("""
%(filtered_orders_cte)s,
sale_rules AS (
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
        %(select_rules)s
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

), sale_commission_lines_team AS (
    SELECT
        MAX(sol.id)::BIGINT *10+3 as id,
        rules.user_id,
        rules.plan_user_id AS plan_user_id,
        MAX(fo.user_id) AS document_user_id,
        MAX(rules.team_id) AS team_id,
        rules.plan_id,
        SUM(%(sale_rates_product)s) AS achieved,
        MAX(fo.currency_id) AS currency_id,
        MAX(fo.date_order) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(fo.company_id) AS achievement_company_id,
        %(select_sales)s
    FROM sale_rules rules
    %(join_sales_team)s
    LEFT JOIN product_product pp
      ON sol.product_id = pp.id
    LEFT JOIN product_template pt
      ON pp.product_tmpl_id = pt.id
    LEFT JOIN product_category pt_categ
      ON pt.categ_id = pt_categ.id
    LEFT JOIN product_category rule_categ
      ON rules.product_categ_id = rule_categ.id
    WHERE rules.team_rule
      AND fo.team_id = rules.team_id
      %(team_condition)s
      %(where_sales)s
    GROUP BY
        fo.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id

), sale_commission_lines_user AS (
    SELECT
        MAX(sol.id)::BIGINT *10+4 as id,
        rules.user_id,
        rules.plan_user_id AS plan_user_id,
        MAX(fo.user_id) AS document_user_id,
        MAX(fo.team_id) AS team_id,
        rules.plan_id,
        SUM(%(sale_rates_product)s) AS achieved,
        MAX(fo.currency_id) AS currency_id,
        MAX(fo.date_order) AS date,
        MAX(rules.company_id) AS plan_company_id,
        MAX(fo.company_id) AS achievement_company_id,
        %(select_sales)s
    FROM sale_rules rules
    %(join_sales_user)s
    LEFT JOIN product_product pp
      ON sol.product_id = pp.id
    LEFT JOIN product_template pt
      ON pp.product_tmpl_id = pt.id
    LEFT JOIN product_category pt_categ
      ON pt.categ_id = pt_categ.id
    LEFT JOIN product_category rule_categ
      ON rules.product_categ_id = rule_categ.id
    WHERE NOT rules.team_rule
      %(user_condition)s
      %(where_sales)s
    GROUP BY
        fo.id,
        rules.plan_id,
        rules.user_id,
        rules.plan_user_id

), sale_commission_lines AS (
    (
    SELECT sale_commission_lines_team.id::bigint as id,
           sale_commission_lines_team.user_id,
           sale_commission_lines_team.plan_user_id,
           sale_commission_lines_team.document_user_id,
           sale_commission_lines_team.team_id,
           sale_commission_lines_team.plan_id,
           sale_commission_lines_team.achieved,
           NULL::numeric AS paid_ratio,
           NULL::text AS payment_state,
           sale_commission_lines_team.currency_id,
           sale_commission_lines_team.date,
           sale_commission_lines_team.plan_company_id,
           sale_commission_lines_team.achievement_company_id,
           sale_commission_lines_team.related_res_id,
           sale_commission_lines_team.related_res_name,
           sale_commission_lines_team.partner_id,
           'sale.order'::text AS related_res_model
      FROM sale_commission_lines_team
    )
    UNION ALL
    (
    SELECT sale_commission_lines_user.id::bigint as id,
           sale_commission_lines_user.user_id,
           sale_commission_lines_user.plan_user_id,
           sale_commission_lines_user.document_user_id,
           sale_commission_lines_user.team_id,
           sale_commission_lines_user.plan_id,
           sale_commission_lines_user.achieved,
           NULL::numeric AS paid_ratio,
           NULL::text AS payment_state,
           sale_commission_lines_user.currency_id,
           sale_commission_lines_user.date,
           sale_commission_lines_user.plan_company_id,
           sale_commission_lines_user.achievement_company_id,
           sale_commission_lines_user.related_res_id,
           sale_commission_lines_user.related_res_name,
           sale_commission_lines_user.partner_id,
           'sale.order'::text AS related_res_model
      FROM sale_commission_lines_user
    )
    )""",
        filtered_orders_cte=self._get_filtered_orders_cte(users=users, teams=teams),
        rate_to_case=self._rate_to_case(sale_rates),
        select_rules=self._select_rules(),
        user_condition=SQL("AND fo.user_id in %s", tuple(users.ids)) if users else SQL(),
        scpu_user_condition=SQL("AND scpu.user_id in %s", tuple(users.ids)) if users else SQL(),
        team_condition=SQL("AND fo.team_id in %s", tuple(teams.ids)) if teams else SQL(),
        scpa_type_condition=SQL("AND scpa.type IN %s", tuple(sale_rates)),
        where_sales=self._where_sales(),
        select_sales=self._select_sales(),
        sale_rates_product=self._get_sale_rates_product(),
        join_sales_user=self._join_sales(join_type='user'),
        join_sales_team=self._join_sales(join_type='team'),
    ), 'sale_commission_lines'

    def _commission_lines_cte(self, users=None, teams=None):
        return [self._achievement_lines_add(users, teams),
                self._achievement_lines_rem(users, teams),
                self._sale_lines(users, teams),
                self._invoices_lines(users, teams)]

    def _commission_lines_query(self, users=None, teams=None):
        ctes = self._commission_lines_cte(users, teams)
        queries = [x[0] for x in ctes]
        table_names = [x[1] for x in ctes]
        # create temporary table to convert currencies
        queries.append(SQL("commission_lines AS (%s)",
            SQL(" UNION ALL ").join(
                SQL("(SELECT * FROM %s)", SQL.identifier(name))
                for name in table_names
            )
        ))
        return SQL(",").join(queries)

    def _pre_achievement_operation(self):
        # Override in other modules. Mostly used in tests
        self.env.flush_all()
        self.env.invalidate_all()
        return
