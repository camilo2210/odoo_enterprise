import json
from collections import defaultdict

from odoo import fields, models
from odoo.tools import SQL, float_compare, groupby

from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10n_VnAccountReportCounterpartMixin(models.AbstractModel):
    """
    Counterpart account ("Số hiệu TK đối ứng") of a journal item, as required by the
    VAS reports S03a-DN and S03b-DN.  Odoo does not store it, so it is reconstructed
    move per move, with a matching strategy depending on the journal type.

    Handlers inheriting this mixin must provide `_get_query(options, current_groupby)`.
    """
    _name = 'l10n_vn.account.report.counterpart.mixin'
    _description = 'VAS Counterpart Account Mixin'

    def _compute_move_counterparts(self, lines):
        """
        Assign counterpart_account_id to each AML line in a move.

        Returns a (possibly expanded) list of row dicts.  A single source line
        may produce multiple output rows when its amount is split across several
        counterpart accounts.  Every returned row has a 'counterpart_account_id'
        key set to an account id (int) or None when no counterpart could be
        determined (uncategorized).
        """
        debit_lines = [ln for ln in lines if ln['balance'] > 0]
        credit_lines = [ln for ln in lines if ln['balance'] < 0]

        if not debit_lines or not credit_lines:
            # Only one side present - no counterpart can be assigned.
            for ln in lines:
                ln['counterpart_account_id'] = None
            return lines

        # Round amounts according to the move's operating currency.
        currency = self.env['res.currency'].browse(lines[0].get('currency_id')) or self.env.company.currency_id
        journal_type = lines[0]['journal_type']

        if lines[0].get('is_tax_closing'):
            return self._match_tax_counterparts(lines, currency)
        if journal_type in ('sale', 'purchase'):
            return self._match_sale_purchase_counterparts(debit_lines, credit_lines, currency)
        return self._match_other_counterparts(debit_lines, credit_lines, currency)

    def _match_sale_purchase_counterparts(self, debit_lines, credit_lines, currency):
        """
        Match lines in sale/purchase journal entries.

        Strategy:
          1. Exact 1-to-1 pairing by identical non-empty label AND equal absolute
             balance.  Each AML is consumed by at most one pair.
          2. Remaining lines - if exactly 1 debit XOR 1 credit remains, that sole
             line is split proportionally across the opposing lines.
          3. Remaining N-to-N: uncategorized (counterpart_account_id = None).
        """
        paired_debit_ids = set()
        paired_credit_ids = set()
        result = []

        # Index credit lines by (name, rounded_abs_balance) for O(1) lookup.
        credit_by_key = defaultdict(list)
        for cl in credit_lines:
            if cl['line_name']:
                credit_by_key[cl['line_name'], currency.round(abs(cl['balance']))].append(cl)

        # Step 1 - label + amount 1-to-1 matching.
        for dl in debit_lines:
            if not dl['line_name'] or dl['id'] in paired_debit_ids:
                continue
            key = dl['line_name'], currency.round(dl['balance'])
            for cl in credit_by_key.get(key, []):
                if cl['id'] not in paired_credit_ids:
                    paired_debit_ids.add(dl['id'])
                    paired_credit_ids.add(cl['id'])
                    dl['counterpart_account_id'] = cl['account_id']
                    result.append(dl)
                    cl['counterpart_account_id'] = dl['account_id']
                    result.append(cl)
                    break

        rem_debits = [ln for ln in debit_lines if ln['id'] not in paired_debit_ids]
        rem_credits = [ln for ln in credit_lines if ln['id'] not in paired_credit_ids]

        if not rem_debits and not rem_credits:
            return result

        # Step 2 - proportional split for 1-to-N or N-to-1 remainder.
        if len(rem_debits) == 1:
            result += self._split_one_vs_many(rem_debits[0], rem_credits, currency)
            return result
        if len(rem_credits) == 1:
            result += self._split_one_vs_many(rem_credits[0], rem_debits, currency)
            return result

        # Step 3 - N-to-N remainder: uncategorized.
        for ln in rem_debits:
            ln['counterpart_account_id'] = None
        result += rem_debits
        for ln in rem_credits:
            ln['counterpart_account_id'] = None
        result += rem_credits
        return result

    def _match_tax_counterparts(self, lines, currency):
        """
        Match lines in TAX journal entries.

        Labels are ignored.  Lines are grouped by account_id on each sign-side,
        then each account group is proportionally distributed against every
        opposing account group.  This produces one merged output row per
        (source account, counterpart account) pair - matching the aggregation
        the report displays for TAX entries.

        Example (one debit account, two credit accounts)::

            Move lines:
                Dr  3331  VAT payable  120
                Cr  1111  Cash         100
                Cr  3388  Other         20

            Result (the Dr 120 is split proportionally, 100/20, across the two
            credit accounts; each credit is attributed to the sole debit account):
                Dr  3331  100  counterpart 1111
                Dr  3331   20  counterpart 3388
                Cr  1111  100  counterpart 3331
                Cr  3388   20  counterpart 3331
        """
        debit_groups = defaultdict(list)
        credit_groups = defaultdict(list)
        for line in lines:
            if line['balance'] > 0:
                debit_groups[line['account_id']].append(line)
            elif line['balance'] < 0:
                credit_groups[line['account_id']].append(line)

        # If both sides have all distinct accounts, no side can be merged into a
        # single representative line. Proportional distribution would be arbitrary,
        # so fall back to uncategorized.
        if len(debit_groups) > 1 and len(credit_groups) > 1:
            for line in lines:
                line['counterpart_account_id'] = None
            return lines

        total_debit = sum(ln['debit'] for g in debit_groups.values() for ln in g)
        total_credit = sum(ln['credit'] for g in credit_groups.values() for ln in g)
        company_currency_id = self.env.company.currency_id.id
        result = []

        for d_account_id, d_lines in debit_groups.items():
            d_total = sum(ln['debit'] for ln in d_lines)
            # Merge all lines in this account group into a single representative row.
            base = dict(d_lines[0])
            base.update({
                'id': min(ln['id'] for ln in d_lines),
                '_original_ids': [ln['id'] for ln in d_lines],  # Track all merged AML ids.
                'line_name': None,  # TAX entries show the move name only.
                'debit': d_total,
                'credit': 0.0,
                'balance': d_total,
                'amount_currency': sum(ln['amount_currency'] or 0 for ln in d_lines) or None,
            })
            if total_credit:
                split_sum = 0
                c_accounts = list(credit_groups.items())
                for i, (c_account_id, c_lines) in enumerate(c_accounts):
                    c_total = sum(ln['credit'] for ln in c_lines)
                    split = currency.round(d_total - split_sum) if i == len(c_accounts) - 1 \
                        else currency.round(d_total * c_total / total_credit)
                    split_sum += split
                    row = dict(base, debit=split, balance=split, counterpart_account_id=c_account_id)
                    if base['amount_currency'] is not None and base['currency_id'] != company_currency_id:
                        row['amount_currency'] = currency.round(base['amount_currency'] * c_total / total_credit)
                    result.append(row)
            else:
                base['counterpart_account_id'] = None
                result.append(base)

        for c_account_id, c_lines in credit_groups.items():
            c_total = sum(ln['credit'] for ln in c_lines)
            base = dict(c_lines[0])
            base.update({
                'id': min(ln['id'] for ln in c_lines),
                '_original_ids': [ln['id'] for ln in c_lines],  # Track all merged AML ids.
                'line_name': None,
                'debit': 0.0,
                'credit': c_total,
                'balance': -c_total,
                'amount_currency': sum(ln['amount_currency'] or 0 for ln in c_lines) or None,
            })
            if total_debit:
                split_sum = 0
                d_accounts = list(debit_groups.items())
                for i, (d_account_id, d_lines) in enumerate(d_accounts):
                    d_total = sum(ln['debit'] for ln in d_lines)
                    split = currency.round(c_total - split_sum) if i == len(d_accounts) - 1 \
                        else currency.round(c_total * d_total / total_debit)
                    split_sum += split
                    row = dict(base, credit=split, balance=-split, counterpart_account_id=d_account_id)
                    if base['amount_currency'] is not None and base['currency_id'] != company_currency_id:
                        row['amount_currency'] = currency.round(base['amount_currency'] * d_total / total_debit)
                    result.append(row)
            else:
                base['counterpart_account_id'] = None
                result.append(base)

        return result

    def _match_other_counterparts(self, debit_lines, credit_lines, currency):
        """
        Match lines in all other journal types (general, cash, bank, etc.).

        Strategy:
          1. Exactly 1 debit OR 1 credit (1-to-1, 1-to-N, N-to-1): proportional
             split at the move level.
          2. N-to-N: label-based matching.  A label group qualifies when its
             total_debit == total_credit AND exactly 1 line exists per side.
          3. Lines with no eligible group: uncategorized.
        """
        # Step 1 - simple moves: exactly 1 debit or 1 credit.
        if len(debit_lines) == 1:
            return self._split_one_vs_many(debit_lines[0], credit_lines, currency)
        if len(credit_lines) == 1:
            return self._split_one_vs_many(credit_lines[0], debit_lines, currency)

        # Step 2 - N-to-N: label-based matching for balanced groups.
        debit_by_label = defaultdict(list)
        credit_by_label = defaultdict(list)
        for ln in debit_lines:
            if ln['line_name']:
                debit_by_label[ln['line_name']].append(ln)
        for ln in credit_lines:
            if ln['line_name']:
                credit_by_label[ln['line_name']].append(ln)

        matched_debit_ids = set()
        matched_credit_ids = set()
        result = []

        for label, d_group in debit_by_label.items():
            c_group = credit_by_label.get(label, [])
            if not c_group:
                continue

            len_d, len_c = len(d_group), len(c_group)

            # Calculate totals to ensure the group balances perfectly
            total_d = sum(d['balance'] for d in d_group)
            total_c = sum(abs(c['balance']) for c in c_group)

            # Only process if the grouped label debits perfectly match the credits
            if float_compare(total_d, total_c, precision_rounding=currency.rounding) != 0:
                continue

            # Scenario A: Strict 1-to-1
            if len_d == 1 and len_c == 1:
                dl, cl = d_group[0], c_group[0]
                matched_debit_ids.add(dl['id'])
                matched_credit_ids.add(cl['id'])

                dl['counterpart_account_id'] = cl['account_id']
                cl['counterpart_account_id'] = dl['account_id']
                result.append(dl)
                result.append(cl)

            # Scenario B: 1 Debit to Many Credits
            elif len_d == 1 and len_c > 1:
                # Add IDs to tracking sets so Step 3 ignores them
                matched_debit_ids.add(d_group[0]['id'])
                matched_credit_ids.update(c['id'] for c in c_group)

                # Reuse your helper method and add to results
                split_lines = self._split_one_vs_many(d_group[0], c_group, currency)
                result.extend(split_lines)

            # Scenario C: Many Debits to 1 Credit
            elif len_d > 1 and len_c == 1:
                # Add IDs to tracking sets so Step 3 ignores them
                matched_debit_ids.update(d['id'] for d in d_group)
                matched_credit_ids.add(c_group[0]['id'])

                # Reuse your helper method and add to results
                split_lines = self._split_one_vs_many(c_group[0], d_group, currency)
                result.extend(split_lines)

        # Step 3 - unmatched lines are uncategorized.
        for ln in debit_lines:
            if ln['id'] not in matched_debit_ids:
                ln['counterpart_account_id'] = None
                result.append(ln)
        for ln in credit_lines:
            if ln['id'] not in matched_credit_ids:
                ln['counterpart_account_id'] = None
                result.append(ln)
        return result

    def _split_one_vs_many(self, sole_line, many_lines, currency):
        """
        Proportionally split one line's amount across multiple opposing lines.

        The sole_line is split into len(many_lines) output rows, each pointing to
        one opposing account.  The last split row receives the remainder to prevent
        cumulative floating-point drift.  Every opposing line is kept as-is,
        pointing back to the sole line's account.
        """
        result = []
        is_debit = sole_line['balance'] > 0
        sole_amount = sole_line['debit'] if is_debit else sole_line['credit']
        total_opposing = sum(abs(ln['balance']) for ln in many_lines) or 1
        company_currency_id = self.env.company.currency_id.id

        split_sum = 0
        amt_cur_sum = 0
        for i, opp in enumerate(many_lines):
            # Opposing line: keep original amounts, point counterpart to sole side.
            opp['counterpart_account_id'] = sole_line['account_id']
            result.append(opp)

            # Sole line split: proportional, last gets remainder.
            opp_weight = abs(opp['balance']) / total_opposing
            split = currency.round(sole_amount - split_sum) if i == len(many_lines) - 1 \
                else currency.round(sole_amount * opp_weight)
            split_sum += split

            split_row = dict(sole_line)
            split_row['counterpart_account_id'] = opp['account_id']
            if is_debit:
                split_row.update({'debit': split, 'credit': 0.0, 'balance': split})
            else:
                split_row.update({'debit': 0.0, 'credit': split, 'balance': -split})

            # Split amount_currency proportionally for multi-currency lines.
            if sole_line.get('amount_currency') is not None \
                    and sole_line.get('currency_id') != company_currency_id:
                ac = currency.round((sole_line['amount_currency'] or 0) - amt_cur_sum) \
                    if i == len(many_lines) - 1 \
                    else currency.round((sole_line['amount_currency'] or 0) * opp_weight)
                amt_cur_sum += ac
                split_row['amount_currency'] = ac

            result.append(split_row)

        return result

    def _fetch_full_move_rows(self, aml_ids):
        """
        Fetch all AML rows for moves that contain the given aml_ids.

        The main query in _get_query is scoped to the account being expanded
        (via forced_domain from the report framework).  This method fetches ALL
        AMLs for the same moves so that _compute_move_counterparts can see both
        the debit and credit sides of each journal entry.

        journal_code, journal_type and is_tax_closing are included here so the
        caller does not need a separate move_journal_map lookup.

        Rows are ordered by AML id so that the counterpart matching - and therefore
        the order of the split rows it produces - is reproducible.
        """
        query = SQL(
            """
            SELECT
                aml.id,
                aml.move_id,
                aml.account_id,
                aml.debit,
                aml.credit,
                aml.balance,
                aml.amount_currency,
                aml.currency_id,
                aml.name                             AS line_name,
                journal.code                         AS journal_code,
                journal.type                         AS journal_type,
                (move.closing_return_id IS NOT NULL) AS is_tax_closing
            FROM  account_move_line aml
            JOIN  account_move    move    ON move.id    = aml.move_id
            JOIN  account_journal journal ON journal.id = move.journal_id
            WHERE aml.move_id IN (
                SELECT move_id FROM account_move_line WHERE id = ANY(%(aml_ids)s)
            )
              AND aml.company_id = ANY(%(company_ids)s)
              AND aml.parent_state = 'posted'
            ORDER BY aml.move_id, aml.id
            """,
            aml_ids=aml_ids,
            company_ids=self.env.companies.ids,
        )
        return list(self.env.execute_query_dict(query))

    def _get_extra_grouping_key_values(self, row):
        """ Handler specific values appended to a journal item grouping key, so that its
        label_builder can name the line without reading back what _get_query returned. """
        return []

    def _report_engine_counterpart_lines(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Custom engine shared by S03a-DN and S03b-DN: it aggregates the rows of the
        handler's own _get_query and, at the journal item level, resolves the counterpart
        of each line (splitting it when its amount is spread over several counterparts). """
        def get_grouping_key(row, groupby_field):
            if groupby_field == 'id_with_accumulated_balance':
                if not row['id']:
                    return f"balance_line_{row['account_id']}"
                key = [fields.Date.to_string(row['date']), row['id']]
                if row.get('counterpart_account_id'):
                    key.append(row['counterpart_account_id'])
                # Carry move_name and is_tax_closing last so the label builder can
                # relabel tax-closing lines without a search, while keeping [0]=date
                # and [1]=aml_id for the base domain/label builders.
                key += [row['move_name'], bool(row.get('is_tax_closing'))]
                key += self._get_extra_grouping_key_values(row)
                return json.dumps(key)
            return row[groupby_field] if groupby_field else None

        query = self._get_query(options, current_groupby)
        raw_rows = list(self.env.execute_query_dict(query))

        # For id_with_accumulated_balance, assign counterpart accounts in Python.
        # The main query is filtered to one account via forced_domain (added by the
        # report framework when expanding an account line), so we fetch ALL AMLs for
        # each move separately to give _compute_move_counterparts both sides.
        if current_groupby == 'id_with_accumulated_balance':
            initial_balance_rows = [r for r in raw_rows if r['id'] is None]
            period_rows = [r for r in raw_rows if r['id'] is not None]
            aml_ids = list({r['id'] for r in period_rows})
            expanded = []
            if aml_ids:
                full_rows = self._fetch_full_move_rows(aml_ids)
                # is_tax_closing is a move-level flag; stamp it on the period rows so
                # it can be carried in the grouping key (see get_grouping_key) and
                # reused by the label builder without an extra search.
                is_tax_closing_by_aml_id = {r['id']: r['is_tax_closing'] for r in full_rows}
                # Run matching on complete moves; map each original AML id to its
                # matched rows.  _original_ids is set by _match_tax_counterparts
                # for merged rows so that all source AML ids are tracked.
                aml_id_to_matched = defaultdict(list)
                for _move_id, full_lines in groupby(full_rows, key=lambda r: r['move_id']):
                    for matched_row in self._compute_move_counterparts(full_lines):
                        for orig_id in matched_row.get('_original_ids') or [matched_row.get('id')]:
                            if orig_id in aml_ids:
                                aml_id_to_matched[orig_id].append(matched_row)

                company_currency_id = self.env.company.currency_id.id
                for period_row in period_rows:
                    period_row['is_tax_closing'] = is_tax_closing_by_aml_id.get(period_row['id'], False)
                    matches = aml_id_to_matched.get(period_row['id'], [])
                    if len(matches) <= 1:
                        # Simple case: one counterpart (or none if unmatched).
                        counterpart_id = matches[0].get('counterpart_account_id') if matches else None
                        period_row['counterpart_account_id'] = counterpart_id
                        expanded.append(period_row)
                    else:
                        # The AML is split across N counterpart accounts.
                        # Replicate the display row with amounts proportional to
                        # the raw-amount ratios from the full-move matching result.
                        is_debit = period_row['balance'] > 0
                        display_amount = period_row['debit'] if is_debit else period_row['credit']
                        raw_total = sum(m['debit'] if is_debit else m['credit'] for m in matches) or 1
                        currency = self.env['res.currency'].browse(period_row.get('currency_id') or company_currency_id)
                        split_sum = 0
                        amt_cur_sum = 0
                        for i, match in enumerate(matches):
                            raw_match = match['debit'] if is_debit else match['credit']
                            if i == len(matches) - 1:
                                split = currency.round(display_amount - split_sum)
                            else:
                                split = currency.round(display_amount * raw_match / raw_total)
                            split_sum += split
                            split_row = dict(period_row)
                            split_row['counterpart_account_id'] = match.get('counterpart_account_id')
                            if is_debit:
                                split_row['debit'] = split
                                split_row['credit'] = 0.0
                                split_row['balance'] = split
                            else:
                                split_row['debit'] = 0.0
                                split_row['credit'] = split
                                split_row['balance'] = -split
                            if period_row.get('amount_currency') is not None \
                                    and period_row.get('currency_id') != company_currency_id:
                                ac_total = period_row['amount_currency'] or 0
                                if i == len(matches) - 1:
                                    ac = currency.round(ac_total - amt_cur_sum)
                                else:
                                    ac = currency.round(ac_total * raw_match / raw_total)
                                amt_cur_sum += ac
                                split_row['amount_currency'] = ac
                            expanded.append(split_row)
            raw_rows = initial_balance_rows + expanded

        counterpart_ids = [r['counterpart_account_id'] for r in raw_rows if r.get('counterpart_account_id')]
        accounts = self.env['account.account'].browse(counterpart_ids)
        counterpart_map = {acc.id: f"{acc.code} {acc.name}" for acc in accounts}

        rows_by_key = defaultdict(lambda: {
            'date': None,
            'partner_name': None,
            'amount_currency': None,
            'currency_id': self.env.company.currency_id.id,
            'debit': 0,
            'credit': 0,
            'balance': 0,
            'balance_debit': 0,
            'balance_credit': 0,
            'counterpart_account': None,
            'has_sublines': True,
        })

        for row in raw_rows:
            aml_key = get_grouping_key(row, current_groupby)
            entry = rows_by_key[aml_key]

            entry['debit'] += row['debit']
            entry['credit'] += row['credit']
            entry['balance'] += row['balance']

            entry['balance_debit'] = entry['balance'] if entry['balance'] > 0 else 0
            entry['balance_credit'] = abs(entry['balance']) if entry['balance'] < 0 else 0

            if current_groupby == 'id_with_accumulated_balance':
                rows_by_key[aml_key]['has_sublines'] = False
                rows_by_key[aml_key]['account_id'] = row['account_id']  # Needed for batching

                if aml_key and 'balance_line' not in aml_key:
                    rows_by_key[aml_key].update({
                        'date': row['date'],
                        'partner_name': row['partner_name'],
                        'line_name': row['line_name'],
                        'account_code': row['account_code'],
                        'account_name': row['account_name'],
                        'move_name': row['move_name'],
                        'counterpart_account': counterpart_map.get(row.get('counterpart_account_id', False)),
                    })
            elif current_groupby == 'account_id':
                rows_by_key[aml_key]['has_sublines'] = True
            elif current_groupby:
                # Any other grouping level (account.move for the general journal S03a-DN)
                # carries its own date and partner.
                rows_by_key[aml_key]['has_sublines'] = True
                rows_by_key[aml_key]['date'] = row.get('date')
                rows_by_key[aml_key]['partner_name'] = row.get('partner_name')

            # A foreign currency amount is only meaningful when the whole group is in that
            # currency; the queries return a NULL currency_id for the groups mixing
            # several of them.  Rows are summed, as a journal item split over several
            # counterpart accounts produces one row per counterpart.
            if row.get('currency_id') and row['currency_id'] != self.env.company.currency_id.id:
                entry['amount_currency'] = (entry['amount_currency'] or 0) + row['amount_currency']
                entry['currency_id'] = row['currency_id']

        expression = next(iter(formulas_dict.values()))

        if not current_groupby:
            default_entry = {
                'date': None,
                'partner_name': None,
                'amount_currency': None,
                'currency_id': self.env.company.currency_id.id,
                'debit': 0,
                'credit': 0,
                'balance': 0,
                'balance_debit': 0,
                'balance_credit': 0,
                'counterpart_account': None,
                'has_sublines': True,
            }
            return {expression: rows_by_key.get(None, default_entry)}

        return {expression: list(rows_by_key.items())}

    # ---------------------------------
    # Non-counterparted lines rendering
    # ---------------------------------

    def _is_uncategorized_line(self, report, line, counterpart_column_index):
        """ Whether the line is a journal item for which no counterpart could be determined.

        Such lines are not shown in place: each handler moves them under a dedicated
        section at the end of the group they belong to (see _append_uncategorized_section).
        """
        if counterpart_column_index is None or not line.id or not line.columns:
            return False

        markup, _model, value = report._get_model_info_from_id(line.id, include_markup=True)
        if not isinstance(markup, dict) or markup.get('groupby') != 'id_with_accumulated_balance':
            return False
        if isinstance(value, str) and value.startswith('balance_line_'):
            # Initial balance rows are not journal items and never carry a counterpart.
            return False

        return not line.columns[counterpart_column_index].no_format

    def _append_uncategorized_section(self, report, options, target_lines, parent_line_id, uncategorized_lines, level):
        """ Append to target_lines a "Non-Counterparted Lines" section under parent_line_id,
        holding the given journal items, whose counterpart could not be determined. """
        section = AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup='uncategorized_section', parent_line_id=parent_line_id),
            name=self.env._("Non-Counterparted Lines"),
            level=level,
            parent_id=parent_line_id,
            columns=[report._build_column_data(None, col, options=options) for col in options.get('columns', [])],
            unfoldable=False,
            unfolded=False,
            custom={'title': self.env._("This journal entry has multiple debit and credit lines whose labels could not be matched 1-to-1. The amounts below are not split proportionally.")},
        )
        target_lines.append(section)

        for uncategorized_line in uncategorized_lines:
            uncategorized_line.parent_id = section.id
            uncategorized_line.level = level + 1
            target_lines.append(uncategorized_line)
