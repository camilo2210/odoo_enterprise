from collections import defaultdict

from odoo import SUPERUSER_ID, api, fields, models
from odoo.tools import SQL


class AccountReconcileModel(models.Model):
    _inherit = 'account.reconcile.model'

    # Technical field to know if the rule was created automatically or by a user.
    created_automatically = fields.Boolean(default=False, copy=False)
    is_asking_for_autopost = fields.Boolean(default=True)
    use_count = fields.Integer()

    def _apply_lines_for_bank_widget(self, residual_amount_currency, residual_balance, partner, st_line):
        """ Apply the reconciliation model lines to the statement line passed as parameter.

        :param residual_amount_currency:    The open amount currency of the statement line in the bank reconciliation widget
                                            expressed in the statement line currency.
        :param residual_balance:            The open balance of the statement line in the bank reconciliation widget
                                            expressed in the company currency.
        :param partner:                     The partner set on the wizard.
        :param st_line:                     The statement line processed by the bank reconciliation widget.
        :return:                            A list of python dictionaries (one per reconcile model line) representing
                                            the journal items to be created by the current reconcile model.
        """
        self.ensure_one()
        currency = st_line.foreign_currency_id or st_line.journal_id.currency_id or st_line.company_currency_id
        vals_list = []
        for line in self.line_ids:
            vals = line._apply_in_bank_widget(
                residual_amount_currency=residual_amount_currency,
                residual_balance=residual_balance,
                partner=line.partner_id or partner,
                st_line=st_line,
            )
            amount_currency = vals['amount_currency']
            balance = vals['balance']

            if currency.is_zero(amount_currency) and st_line.company_currency_id.is_zero(balance):
                continue

            vals_list.append(vals)
            residual_amount_currency -= amount_currency
            residual_balance -= balance

        return vals_list

    @api.model
    def get_available_reconcile_model_per_statement_line(self, statement_line_ids):
        self.check_access('read')
        self.env['account.reconcile.model'].flush_model()
        self.env['account.bank.statement.line'].flush_model()
        self.env.cr.execute(SQL(
            """
            WITH matching_journal_ids AS (
                    SELECT account_reconcile_model_id,
                           ARRAY_AGG(account_journal_id) AS ids
                      FROM account_journal_account_reconcile_model_rel
                  GROUP BY account_reconcile_model_id
                 ),
                 matching_partner_ids AS (
                    SELECT account_reconcile_model_id,
                           ARRAY_AGG(res_partner_id) AS ids
                      FROM account_reconcile_model_res_partner_rel
                  GROUP BY account_reconcile_model_id
                 )

          SELECT st_line.id AS st_line_id,
                 array_agg(reco_model.id ORDER BY reco_model.created_automatically ASC NULLS FIRST, reco_model.sequence ASC, reco_model.id ASC) AS reco_model_ids,
                 array_agg(reco_model.name ORDER BY reco_model.created_automatically ASC NULLS FIRST, reco_model.sequence ASC, reco_model.id ASC) AS reco_model_names
            FROM account_bank_statement_line st_line
       LEFT JOIN LATERAL (
                   SELECT DISTINCT reco_model.id,
                          reco_model.sequence,
                          reco_model.created_automatically,
                          COALESCE(reco_model.name -> %(lang)s, reco_model.name -> 'en_US') as name
                     FROM account_reconcile_model reco_model
                LEFT JOIN matching_journal_ids ON reco_model.id = matching_journal_ids.account_reconcile_model_id
                LEFT JOIN matching_partner_ids ON reco_model.id = matching_partner_ids.account_reconcile_model_id
                LEFT JOIN account_reconcile_model_line reco_model_line ON reco_model_line.model_id = reco_model.id
                    WHERE (matching_journal_ids.ids IS NULL OR st_line.journal_id = ANY(matching_journal_ids.ids))
                      AND (matching_partner_ids.ids IS NULL OR st_line.partner_id = ANY(matching_partner_ids.ids))
                      AND (
                          CASE COALESCE(reco_model.match_amount, '')
                              WHEN 'lower' THEN st_line.amount <= reco_model.match_amount_max
                              WHEN 'greater' THEN st_line.amount >= reco_model.match_amount_min
                              WHEN 'between' THEN
                                  (st_line.amount BETWEEN reco_model.match_amount_min AND reco_model.match_amount_max) OR
                                  (st_line.amount BETWEEN reco_model.match_amount_max AND reco_model.match_amount_min)
                              ELSE TRUE
                          END
                          )
                      AND (
                              reco_model.match_label IS NULL
                              OR (
                                  reco_model.match_label = 'contains'
                                   AND (
                                      st_line.payment_ref IS NOT NULL AND st_line.payment_ref ILIKE '%%' || reco_model.match_label_param || '%%'
                                      OR st_line.transaction_details IS NOT NULL AND st_line.transaction_details::TEXT ILIKE '%%' || reco_model.match_label_param || '%%'
                                   )
                              ) OR (
                                  reco_model.match_label = 'not_contains'
                                  AND NOT (
                                      st_line.payment_ref IS NOT NULL AND st_line.payment_ref ILIKE '%%' || reco_model.match_label_param || '%%'
                                      OR st_line.transaction_details IS NOT NULL AND st_line.transaction_details::TEXT ILIKE '%%' || reco_model.match_label_param || '%%'
                                  )
                              ) OR (
                                  reco_model.match_label = 'match_regex'
                                  AND (
                                      st_line.payment_ref IS NOT NULL AND st_line.payment_ref ~* reco_model.match_label_param
                                      OR st_line.transaction_details IS NOT NULL AND st_line.transaction_details::TEXT ~* reco_model.match_label_param
                                  )
                              )
                          )
                      AND reco_model.company_id = st_line.company_id
                      AND reco_model.trigger = 'manual'
                      AND reco_model_line.account_id IS NOT NULL
                      AND reco_model.active IS TRUE
                 ) AS reco_model ON TRUE
           WHERE st_line.id IN %(statement_lines)s
             AND reco_model.id IS NOT NULL
           GROUP BY st_line.id
            """,
            lang=self.env.lang,
            statement_lines=tuple(statement_line_ids),
        ))
        query_result = self.env.cr.fetchall()
        return {
            st_line_id: [
                {'id': model_id, 'display_name': model_name}
                for (model_id, model_name)
                in zip(model_ids, model_names)
            ]
            for st_line_id, model_ids, model_names
            in query_result
        }

    def _apply_reconcile_models(self, statement_lines, remaining_st_line_ids=None, account_ids=None):
        if not self or not statement_lines:
            return
        self.env['account.reconcile.model'].flush_model()
        statement_lines.flush_recordset(['journal_id', 'amount', 'amount_residual', 'transaction_details', 'payment_ref', 'partner_id', 'company_id'])
        self.env.cr.execute(SQL(r"""
            WITH matching_journal_ids AS (
                    SELECT account_reconcile_model_id,
                           ARRAY_AGG(account_journal_id) AS ids
                      FROM account_journal_account_reconcile_model_rel
                  GROUP BY account_reconcile_model_id
                 ),
                 matching_partner_ids AS (
                    SELECT account_reconcile_model_id,
                           ARRAY_AGG(res_partner_id) AS ids
                      FROM account_reconcile_model_res_partner_rel
                  GROUP BY account_reconcile_model_id
                 ),
                 model_fees AS (
                    SELECT model_fees.id,
                           model_fees.trigger,
                           matching_journal_ids.ids AS journal_ids
                      FROM account_reconcile_model model_fees
                      JOIN ir_model_data imd ON model_fees.id = imd.res_id
                      JOIN account_reconcile_model_line model_lines ON model_lines.model_id = model_fees.id
                 LEFT JOIN matching_journal_ids ON model_fees.id = matching_journal_ids.account_reconcile_model_id
                     WHERE imd.module = 'account'
                       AND imd.name LIKE 'account\_reco\_model\_fee\_%%'
                       AND model_fees.active IS TRUE
                       AND model_lines.account_id IS NOT NULL
                 )

          SELECT st_line.id AS st_line_id,
                 COALESCE(reco_model.id, model_fees.id) AS reco_model_id,
                 COALESCE(reco_model.trigger, model_fees.trigger) AS trigger
            FROM account_bank_statement_line st_line
            JOIN account_move move ON st_line.move_id = move.id
       LEFT JOIN LATERAL (
                   SELECT reco_model.id,
                          reco_model.trigger
                     FROM account_reconcile_model reco_model
                LEFT JOIN matching_journal_ids ON reco_model.id = matching_journal_ids.account_reconcile_model_id
                LEFT JOIN matching_partner_ids ON reco_model.id = matching_partner_ids.account_reconcile_model_id
                    WHERE (matching_journal_ids.ids IS NULL OR st_line.journal_id = ANY(matching_journal_ids.ids))
                      AND (matching_partner_ids.ids IS NULL OR st_line.partner_id = ANY(matching_partner_ids.ids))
                      AND (
                              CASE COALESCE(reco_model.match_amount, '')
                                  WHEN 'lower' THEN st_line.amount <= reco_model.match_amount_max
                                  WHEN 'greater' THEN st_line.amount >= reco_model.match_amount_min
                                  WHEN 'between' THEN
                                      (st_line.amount BETWEEN reco_model.match_amount_min AND reco_model.match_amount_max) OR
                                      (st_line.amount BETWEEN reco_model.match_amount_max AND reco_model.match_amount_min)
                                  ELSE TRUE
                              END
                          )
                      AND (
                              reco_model.match_label IS NULL
                              OR (
                                  reco_model.match_label = 'contains'
                                   AND (
                                      st_line.payment_ref IS NOT NULL AND st_line.payment_ref ILIKE '%%' || reco_model.match_label_param || '%%'
                                      OR st_line.transaction_details IS NOT NULL AND st_line.transaction_details::TEXT ILIKE '%%' || reco_model.match_label_param || '%%'
                                      OR move.narration IS NOT NULL AND move.narration::TEXT ILIKE '%%' || reco_model.match_label_param || '%%'
                                   )
                              ) OR (
                                  reco_model.match_label = 'not_contains'
                                  AND NOT (
                                      st_line.payment_ref IS NOT NULL AND st_line.payment_ref ILIKE '%%' || reco_model.match_label_param || '%%'
                                      OR st_line.transaction_details IS NOT NULL AND st_line.transaction_details::TEXT ILIKE '%%' || reco_model.match_label_param || '%%'
                                      OR move.narration IS NOT NULL AND move.narration::TEXT ILIKE '%%' || reco_model.match_label_param || '%%'
                                  )
                              ) OR (
                                  reco_model.match_label = 'match_regex'
                                  AND (
                                      st_line.payment_ref IS NOT NULL AND st_line.payment_ref ~* reco_model.match_label_param
                                      OR st_line.transaction_details IS NOT NULL AND st_line.transaction_details::TEXT ~* reco_model.match_label_param
                                      OR move.narration IS NOT NULL AND move.narration::TEXT ~* reco_model.match_label_param
                                  )
                              )
                          )
                      AND reco_model.id IN %s
                      AND reco_model.can_be_proposed IS TRUE
                      AND reco_model.company_id = st_line.company_id
                 ORDER BY reco_model.created_automatically ASC NULLS FIRST, reco_model.sequence ASC, reco_model.id ASC
                    LIMIT 1
                 ) AS reco_model ON TRUE
       LEFT JOIN LATERAL (
                   SELECT model_fees.id,
                          model_fees.trigger
                     FROM model_fees
                    WHERE st_line.journal_id = ANY(model_fees.journal_ids)
                   -- Show model fees if matched amount was 3 %% higher than incoming statement line amount
                      AND SIGN(st_line.amount) > 0
                      AND SIGN(st_line.amount_residual) > 0
                      AND ABS(st_line.amount_residual) < 0.03 * st_line.amount / 1.03
                 ) AS model_fees ON TRUE
           WHERE st_line.id IN %s
        """, tuple(self.ids), tuple(statement_lines.ids)))

        query_result = self.env.cr.fetchall()

        processed_st_line_ids = set()
        matching_rules = defaultdict(lambda: self.env['account.bank.statement.line'])
        # apply the found suitable reco models on the statement lines
        for st_line_id, reco_model_id, reco_model_trigger in query_result:
            if st_line_id in processed_st_line_ids or reco_model_id is None:
                continue

            st_line = self.env['account.bank.statement.line'].browse(st_line_id).with_prefetch(statement_lines.ids)
            reco_model = self.env['account.reconcile.model'].browse(reco_model_id).with_prefetch(self.ids)

            if reco_model_trigger == 'manual':
                st_line._action_manual_reco_model(reco_model_id)
            elif reco_model.rule_type == 'matching_rule':
                matching_rules[reco_model] += st_line
            else:
                reco_model.with_user(SUPERUSER_ID)._trigger_reconciliation_model(st_line.with_user(SUPERUSER_ID))
            processed_st_line_ids.add(st_line_id)

        for matching_rule, st_lines in matching_rules.items():
            st_lines._try_auto_matching_and_reconcile(st_lines.move_id.ids, remaining_st_line_ids, account_ids, matching_rule=matching_rule)

        return remaining_st_line_ids

    def _trigger_reconciliation_model(self, statement_line):
        self.ensure_one()
        liquidity_line, suspense_line, other_lines = statement_line._seek_for_lines()

        amls_to_create = list(
            self._apply_lines_for_bank_widget(
                residual_amount_currency=sum(suspense_line.mapped('amount_currency')),
                residual_balance=sum(suspense_line.mapped('balance')),
                partner=statement_line.partner_id,
                st_line=statement_line,
            )
        )
        # Get the original base lines and tax lines before the creation of new lines
        if any(aml.get('tax_ids') for aml in amls_to_create):
            original_base_lines, original_tax_lines = statement_line._prepare_for_tax_lines_recomputation()

        statement_line._set_move_line_to_statement_line_move(liquidity_line + other_lines, amls_to_create)

        # Now that the new lines have been added, we can recompute the taxes
        if any(aml.get('tax_ids') for aml in amls_to_create):
            _new_liquidity_line, new_suspense_line, _new_other_lines = statement_line._seek_for_lines()
            new_lines = statement_line.line_ids - (liquidity_line + other_lines + new_suspense_line)
            statement_line._create_tax_lines(original_base_lines, original_tax_lines, new_lines)

        if self.next_activity_type_id:
            statement_line.activity_schedule(
                activity_type_id=self.next_activity_type_id.id,
                user_id=self.env.user.id,
            )

    def _trigger_matching_rule(self, st_line, aml_ids, amls_amount_residual, processed_st_line_ids, allow_partial=True):
        """ Reconcile amls with the st_line, respecting the matching order and the payment tolerance of the matching_rule.
            We loop into aml_ids until we hit the payment tolerance or the statement line is reconciled or we matched all
            account.move.line.
            Once we set the aml on the statement line, if we hit the tolerance, apply the matching rule counterparts items.

            :param st_line: The statement line to reconcile.
            :param aml_ids: List of account.move.line ids to reconcile with the statement line. This list should be the same
                            order as the one defined on the matching rule.
            :param amls_amount_residual: List of account.move.line amount_residual, mapped with aml_ids.
            :param processed_st_line_ids: Set of statement line ids, to keep track of reconciled lines.
            :param allow_partial: Flag to know if we want to allow partial reconciliation.
        """
        def _amount_matches_or_exceeds(st_line_amount, aml_amount):
            return (
                (st_line_amount < 0 and aml_amount < -st_line_amount) or
                (st_line_amount > 0 and aml_amount > -st_line_amount)
            )

        self.ensure_one()
        matched_aml_ids = []
        aml_amount_sum = 0
        st_line_amount_residual = st_line.amount_residual
        matching_tolerance = False
        if self.payment_tolerance_type == 'percentage':
            tolerance = abs(st_line.amount * (self.payment_tolerance / 100))
        else:
            tolerance = self.payment_tolerance
        amls = self.env['account.move.line'].search_fetch(domain=[('id', 'in', aml_ids)], field_names=['reconciled']).grouped('id')
        # We loop until:
        #     1. The amount of matched aml exceed the st_line residual amount -> We'll do a partial reconcile on the last aml
        #     2. We pop all amls
        #     3. We hit the tolerance -> We'll do a full reconcile on the last aml, then apply the counterparts items
        #
        # aml_ids & amls_amount_residual are ordered the same way
        for aml_id, aml_amount_residual in zip(aml_ids, amls_amount_residual):
            if not (
                _amount_matches_or_exceeds(st_line.amount_residual, aml_amount_sum) and
                not matching_tolerance
            ):
                break

            aml = amls.get(aml_id)
            if aml.reconciled:
                continue
            # If the aml amount is between the tolerance boundaries, we fully match the aml then stop the loop
            if tolerance and -st_line_amount_residual - tolerance <= aml_amount_residual <= -st_line_amount_residual + tolerance:
                matched_aml_ids.append(aml_id)
                matching_tolerance = True
                processed_st_line_ids.add(st_line.id)
            # We still check if the st_line residual amount is not in the tolerance boundaries to keep the suspense line in the boundaries
            elif abs(st_line_amount_residual) > tolerance and allow_partial:
                matched_aml_ids.append(aml_id)
                st_line_amount_residual += aml_amount_residual
                aml_amount_sum += aml_amount_residual
        # Set the matched aml on the st_line, the partial reconcile shouldn't be allowed if we hit the tolerance
        st_line.set_line_bank_statement_line(matched_aml_ids, allow_partial=not matching_tolerance and allow_partial)
        self.env['account.move.line'].browse(matched_aml_ids).reconcile_model_id = self.id
        # If the tolerance has been hit, trigger the reco model to apply the counterpart items if any
        if matching_tolerance:
            self._trigger_reconciliation_model(st_line)

    def trigger_reconciliation_model(self, statement_line_ids):
        self.ensure_one()

        if self.is_asking_for_autopost:
            self.use_count += 1

        statement_lines = self.env['account.bank.statement.line'].browse(statement_line_ids).exists()
        for statement_line in statement_lines:
            self._trigger_reconciliation_model(statement_line)

    def write(self, vals):
        res = super().write(vals)
        unreconciled_domain = [
            *self._check_company_domain(self.env.company),
            ('is_reconciled', '=', False),
        ]
        unreconciled_statement_lines = self.env['account.bank.statement.line'].search(unreconciled_domain)
        if unreconciled_statement_lines:
            move_lines = self.env['account.move.line'].search([
                ('reconcile_model_id', 'in', self.ids),
                ('move_id.statement_line_id', 'any', unreconciled_domain)
            ])
            move_lines.filtered(
                lambda line:
                line.account_id == line.move_id.journal_id.suspense_account_id
            ).reconcile_model_id = False
            self.filtered(lambda model: model.rule_type == 'reco_model')._apply_reconcile_models(unreconciled_statement_lines)

        return res

    @api.model_create_multi
    def create(self, vals_list):
        reco_models = super().create(vals_list)
        unreconciled_statement_lines = self.env['account.bank.statement.line'].search([
            *self._check_company_domain(self.env.company),
            ('is_reconciled', '=', False),
        ])
        if unreconciled_statement_lines:
            reco_models.filtered(lambda model: model.rule_type == 'reco_model')._apply_reconcile_models(unreconciled_statement_lines)

        return reco_models

    def action_archive(self):
        res = super().action_archive()
        unreconciled_statement_lines = self.env['account.bank.statement.line'].search([
            *self._check_company_domain(self.env.company),
            ('is_reconciled', '=', False),
            ('line_ids.reconcile_model_id', 'in', self.ids),
        ])
        if unreconciled_statement_lines:
            unreconciled_statement_lines.line_ids.filtered(
                lambda line:
                line.account_id == line.move_id.journal_id.suspense_account_id
            ).reconcile_model_id = False
        return res

    def _order_to_sql(self, table, order, reverse=False):
        sql_order = super()._order_to_sql(table, order, reverse)
        if journal_id := self.env.context.get('active_id') or self.env.context.get('default_journal_id'):
            return SQL(
                """EXISTS (
                    SELECT 1
                    FROM account_journal_account_reconcile_model_rel
                    WHERE account_reconcile_model_id = %(reco_model_id)s
                      AND account_journal_id = %(journal_id)s
                ) DESC, %(sql_order)s""",
                reco_model_id=table.id,
                journal_id=journal_id,
                sql_order=sql_order,
            )

        return sql_order
