import json

from collections import deque
from datetime import date

from odoo import api, models, fields
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import SQL

SNAPSHOTABLE_ENGINES = {}


def snapshotable_engine(result_aggregators, sub_engine_of=None, version=1):
    """ Decorator to be used on engine functions to mark them as able to use account.report.snapshot objects in their computation.
    When an engine is snapshotable, each call to it will search for a snapshot covering the desired period. If the covering is full, the result
    from the snapshot will directly be used, and no report query will be run at all. If it is partial, a call to the engine will be made, forcing
    the considered period to only consist of the gap between the snapshot and what we want to compute. The result of this call will then be combined
    with the snapshot's result, hence forming the global result for this engine call. This also works in multi-company, where each company can
    have its own snapshots, at different dates.

    Note that any report engine cannot be made snapshotable. To be snapshotable, an engine must be composable: it must be possible to compute it by
    part (we call those parts result partitions). Merging the different parts must give the exact same result as computing the full period directly.
    The engine must allow being split like that by company and date.

    Another important point is warnings won't be kept by snapshots. So, only the actual calls to the engine will generate them. This is considered
    acceptable, since snapshots are generated for locked periods, and it's unlikely the data in such periods require any kind of warning.

    This decorator can be used on both standard and custom engines.
    """
    def decorator(engine_func):
        engine_main_func_name = sub_engine_of or engine_func.__name__

        def snapshotable_engine_wrapper(self, options, date_scope, formulas_dict, groupby, warnings=None):
            # For custom engines, 'self' is the custom handler, not the report.
            report = self if self._name == 'account.report' else self.env['account.report'].browse(options['report_id'])
            if not report.enable_snapshots:
                return engine_func(self, options, date_scope, formulas_dict, groupby, warnings=warnings)

            snapshots = report.env['account.report.snapshot']._get_latest_snapshots(engine_main_func_name, version, options, date_scope, formulas_dict, groupby)

            snapshot_domain = None
            need_to_call_engine = True
            if len(set(snapshots.mapped('date'))) == 1 and len(snapshots) == len(options['companies']):
                if fields.Date.to_string(snapshots[0].date) != report._get_date_bounds_info(options, date_scope)[1]:
                    snapshot_domain = [('date', '>', snapshots[0].date)]
                else:
                    # We don't want to call the engine at all: the snapshots already cover everything
                    need_to_call_engine = False
            elif snapshots:
                snapshot_domain_terms = []
                for snapshot in snapshots:
                    snapshot_domain_terms.append([('company_id', '=', snapshot.company_id.id), ('date', '>', snapshot.date)])

                company_ids_without_snapshot = set(report.env['account.report'].get_report_company_ids(options)) - set(snapshots.mapped('company_id').ids)
                if company_ids_without_snapshot:
                    snapshot_domain_terms.append([('company_id', 'in', tuple(company_ids_without_snapshot))])

                snapshot_domain = Domain.OR(snapshot_domain_terms)

            result_partitions = snapshots._read_result_partitions()

            if need_to_call_engine:
                if snapshot_domain:
                    options = {
                        **options,
                        'forced_domain': list(Domain.AND([options.get('forced_domain', []), snapshot_domain])),
                    }

                result_partitions.append(engine_func(self, options, date_scope, formulas_dict, groupby, warnings=warnings))

            return report.env['account.report.snapshot']._merge_result_partitions(result_partitions, result_aggregators)

        snapshotable_engine_data = {'version': version, 'result_aggregators': result_aggregators}
        if sub_engine_of:
            snapshotable_engine_data['sub_engine'] = engine_func.__name__

        SNAPSHOTABLE_ENGINES[engine_main_func_name] = snapshotable_engine_data
        return snapshotable_engine_wrapper

    return decorator


class AccountReportSnapshot(models.Model):
    _name = 'account.report.snapshot'
    _description = "Accounting Report Snapshot"

    report_id = fields.Many2one(comodel_name='account.report', required=True, index='btree')
    engine_func = fields.Char(required=True)
    engine_version = fields.Integer(required=True)
    serialized_options = fields.Json(required=True)
    serialized_formulas_dict = fields.Json(required=True)
    date_scope = fields.Char(required=True)
    company_id = fields.Many2one(comodel_name='res.company', required=True)
    date = fields.Date(required=True)
    groupby = fields.Char()
    result = fields.Json(required=True)

    _unique = models.Constraint(
        "UNIQUE(serialized_options, serialized_formulas_dict, engine_func, engine_version, date_scope, company_id, report_id, date, groupby)",
        "You cannot create duplicate report snapshots for the same company, report and date with the same engine parameters.",
    )

    def _register_hook(self):
        rslt = super()._register_hook()

        # Clean snapshots made for previous versions of the engines, and trigger the snapshot cron if necessary.
        # With this, we can ensure a fix made in stable in the computation of an engine will trigger the proper recomputation of the snapshots
        outdated_snapshots_domains = []
        for engine_func_name, engine_info in SNAPSHOTABLE_ENGINES.items():
            outdated_snapshots_domains.append([
                ('engine_func', '=', engine_func_name),
                ('engine_version', '<', engine_info['version']),
            ])

        outdated_snapshots = self.env['account.report.snapshot'].search(Domain.OR(outdated_snapshots_domains))
        outdated_snapshots.unlink()

        if outdated_snapshots:
            self.env.ref('account_reports.ir_cron_create_snapshots')._trigger()

        return rslt

    @api.model
    def _cron_create_snapshots(self):
        all_snapshots_to_create_params = self._get_snapshots_to_create_params()

        asked_creation_date = None
        created_snapshot = None
        for report, col_group_options, engine, date_scope, formulas_dict, groupby in all_snapshots_to_create_params:
            asked_creation_date = fields.Date.from_string(col_group_options['date']['date_to'])
            created_snapshot = self._make_snapshot(report, col_group_options, engine, date_scope, formulas_dict, groupby, years_spread=5)
            if created_snapshot:
                # The next ones will be run in a future execution of the cron
                break

        # If the iterator still has elements to treat, we possibly have more snapshots left to generate.
        # If the created snapshot's date is not the one that was asked for, it means it was created in the past, because of years_spread. We then
        # need to re-call the cron to fill the gap, until all required snapshots have been generated in the past.
        if next(all_snapshots_to_create_params, None) or (created_snapshot and created_snapshot.date != asked_creation_date):
            self.env.ref('account_reports.ir_cron_create_snapshots')._trigger()

        return created_snapshot

    @api.model
    def _cron_garbage_collect_snapshots(self):
        generic_tax_report = self.env.ref('account.generic_tax_report')

        snapshot_deletion_domains = []
        for company in self.env['res.company'].search([]).with_context(ignore_exceptions=True):
            fy_hard_lock_date = max(company.user_fiscalyear_lock_date, company.user_hard_lock_date)

            snapshot_deletion_domains.append([
                *([('date', '>', fy_hard_lock_date)] if fy_hard_lock_date != date.min else []),
                ('company_id', '=', company.id),
                ('report_id.root_report_id', '!=', generic_tax_report.id),
            ])

            snapshot_deletion_domains.append([
                *([('date', '>', company.user_tax_lock_date)] if company.user_tax_lock_date != date.min else []),
                ('company_id', '=', company.id),
                ('report_id.root_report_id', '=', generic_tax_report.id),
            ])

        self.env['account.lock_exception'].flush_model()
        self.env.cr.execute(SQL("""
            SELECT DISTINCT ON (company_id, lock_date_field)
                company_id,
                lock_date_field,
                lock_date,
                end_datetime
            FROM account_lock_exception
            WHERE
                lock_date_field IN ('fiscalyear_lock_date', 'tax_lock_date')
            ORDER BY company_id, lock_date_field, create_date
        """))

        for (company_id, lock_date_field, lock_date, end_datetime) in self.env.cr.fetchall():
            # For simplicity, we consider all branches are impacted, and need garbage collection of their snapshots, even if they have a more
            # restrictive lock date themselves.
            impacted_branches = self.env['res.company'].search([('id', 'child_of', company_id)])

            exception_violation_domain = [('company_id', 'in', impacted_branches.ids)]
            if lock_date:
                exception_violation_domain.append(('date', '>', lock_date))

            if end_datetime:
                exception_violation_domain.append(('create_date', '<', end_datetime))

            if lock_date_field == 'tax_lock_date':
                exception_violation_domain.append(('report_id.root_report_id', '=', generic_tax_report.id))

            snapshot_deletion_domains.append(exception_violation_domain)

        snapshots_to_unlink = self.env['account.report.snapshot'].search(Domain.OR(snapshot_deletion_domains))
        snapshots_to_unlink.unlink()

        refresh_cron = self.env.ref('account_reports.ir_cron_create_snapshots')
        if not self.env['ir.cron.trigger'].search([('cron_id', '=', refresh_cron.id)], limit=1):
            # If no call is planned in the future (as it would be the case with lock date exceptions), trigger the refresh
            refresh_cron._trigger()

    @api.model
    def _get_snapshots_to_create_params(self):
        call_time = fields.Datetime.now()
        reports_to_snapshot = self.env['account.report'].search([('enable_snapshots', '=', True)])
        all_companies = self.env['res.company'].search([])
        generic_tax_report = self.env.ref('account.generic_tax_report')

        for report in reports_to_snapshot:
            is_tax_report = (report.root_report_id or report) == generic_tax_report

            expressions_by_evaluation_groupby = {}
            for line in report.line_ids:
                # None => line's own totals
                evaluation_groupbys = {None}
                if line.foldability == 'always_unfolded' and (line_groupby := line._get_groupby()):
                    # The first groupby level of an always unfolded line is evaluated on every rendering of the report,
                    # so it needs its own snapshots as well
                    evaluation_groupbys.add(line_groupby)

                for evaluation_groupby in evaluation_groupbys:
                    expressions_by_evaluation_groupby.setdefault(evaluation_groupby, self.env['account.report.expression'])
                    expressions_by_evaluation_groupby[evaluation_groupby] += line.expression_ids

            for company in all_companies.with_context(ignore_exceptions=True):
                lock_date = company.user_tax_lock_date if is_tax_report else max(company.user_fiscalyear_lock_date, company.user_hard_lock_date)

                if lock_date == date.min or not report._is_available_for(company):
                    continue

                # Don't generate anything if a lock date exception is covering this period. When it expires, the exception will trigger a new call to the cron
                exception = self.env['account.lock_exception'].search([
                    ('company_id', 'in', company.parent_ids.ids),
                    ('tax_lock_date' if is_tax_report else 'fiscalyear_lock_date', '<', lock_date),
                    '|', ('end_datetime', '=', False), ('end_datetime', '>', call_time),
                ], limit=1)

                if exception:
                    continue

                options = report.with_context(allowed_company_ids=company.ids).get_options({
                    'date': {'date_to': fields.Date.to_string(lock_date), 'period_type': 'custom'},
                    'no_report_reroute': True,
                })

                if self._snapshot_forbidden(options):
                    continue

                for evaluation_groupby, expressions in expressions_by_evaluation_groupby.items():
                    for col_group_options in report._split_options_per_column_group(options).values():
                        grouped_formulas_by_engine = report._group_expression_formulas(col_group_options, expressions, groupby_to_expand=evaluation_groupby)

                        for engine, grouped_formulas in grouped_formulas_by_engine.items():
                            for (date_scope, groupby), formulas_dict in grouped_formulas.items():
                                if date_scope in ['from_beginning', 'to_beginning_of_fiscalyear', 'to_beginning_of_period']:
                                    yield report, col_group_options, engine, date_scope, formulas_dict, groupby

    @api.model
    def _make_snapshot(self, report, col_group_options, engine, date_scope, formulas_dict, groupby, years_spread=0):
        """ Tries creating an account.report.snapshot object for the provided report engine parameters.
        If engine is not snapshotable or a snapshot already exists for those parameters, None will be returned. Else, a new snapshot will be created
        and returned.

        The years_spread parameter is used to make sure snapshots are spread homogenously through time, so that period comparison in reports can
        benefit from them. When set to a non-zero value, it will change the period of the generated snapshot if the last snapshot (or the first aml
        of the accounting if there was not snapshot) is more than one year before the date_to of the options. The chosen date will be maximum
        years_spread years before the date_to, or 1 year after the last snapshot, if it was more recent than that. This option is especially useful
        when regenerating snapshots after garbage-collection, for example because of a change in an engine version (probably coming from a bugfix).
        """
        company_ids = report.get_report_company_ids(col_group_options)
        company = self.env['res.company'].browse(company_ids)
        if len(company) > 1:
            raise UserError(self.env._("Snapshots of accounting reports should be made one company at a time."))

        engine_main_func_name = report._get_engine_function_name(engine)
        if engine_main_func_name not in SNAPSHOTABLE_ENGINES:
            return None

        # Aim the options to the lock date, so that the engine call is snapshotted up to it.
        col_group_options = self._align_options_with_snapshot_date(report, col_group_options, date_scope, fields.Date.to_date(col_group_options['date']['date_to']))
        snapshot_date = fields.Date.to_date(report._get_date_bounds_info(col_group_options, date_scope)[1])

        latest_snapshot = self._get_latest_snapshots(engine_main_func_name, SNAPSHOTABLE_ENGINES[engine_main_func_name]['version'], col_group_options, date_scope, formulas_dict, groupby)
        if latest_snapshot and latest_snapshot.date == snapshot_date:
            return None

        if years_spread:
            next_snapshot_fy_end = None
            if latest_snapshot:
                next_snapshot_fy_end = fields.Date.add(company.compute_fiscalyear_dates(latest_snapshot.date)['date_to'], years=1)
            else:
                aml_data = self.env['account.move.line'].search_read([('company_id', '=', company_ids[0])], fields=['date'], order='date ASC', limit=1)
                if aml_data:
                    next_snapshot_fy_end = company.compute_fiscalyear_dates(aml_data[0]['date'])['date_to']

            if next_snapshot_fy_end and next_snapshot_fy_end < snapshot_date:
                # Instead of creating the snapshot at the date to, we create after the last snapshot, or years_spread years ago, at the end of a fiscal
                # year, if it's closer. Doing it that way ensures we keep comparisons working when regenerating snapshots. A more naive approach where
                # we only regenerate a snapshot at the current lock date would have made all comparisons super slow.
                years_before_fy_end = company.compute_fiscalyear_dates(fields.Date.subtract(snapshot_date, years=years_spread))['date_to']
                scoped_date_to = max(years_before_fy_end, next_snapshot_fy_end)
                col_group_options = self._align_options_with_snapshot_date(report, col_group_options, date_scope, scoped_date_to)
                snapshot_date = fields.Date.to_date(report._get_date_bounds_info(col_group_options, date_scope)[1])

        function_to_call = report._get_custom_report_function(SNAPSHOTABLE_ENGINES[engine_main_func_name].get('sub_engine', engine_main_func_name), 'engine')
        engine_result = function_to_call(col_group_options, date_scope, formulas_dict, groupby)

        json_friendly_engine_result = {
            ','.join(str(expr.id) for expr in expressions): formula_res
            for expressions, formula_res in engine_result.items()
        }

        return self.env['account.report.snapshot'].create([{
            'serialized_options': self._get_serializable_options(col_group_options),
            'serialized_formulas_dict': self._get_serializable_formulas_dict(formulas_dict),
            'engine_func': engine_main_func_name,
            'engine_version': SNAPSHOTABLE_ENGINES[engine_main_func_name]['version'],
            'date_scope': date_scope,
            'result': json_friendly_engine_result,
            'company_id': company_ids[0],
            'report_id': report.id,
            'date': snapshot_date,
            'groupby': groupby,
        }])

    @api.model
    def _align_options_with_snapshot_date(self, report, col_group_options, date_scope, snapshot_date):
        """ Returns the options making date_scope evaluate the accounting up to snapshot_date. """
        # The 'to_beginning_of_*' scopes stop right before the period (or fiscal year) of the options; aiming
        # them at the day after covers snapshot_date.
        if date_scope == 'to_beginning_of_period':
            date_option = {**col_group_options['date'], 'date_from': fields.Date.to_string(fields.Date.add(snapshot_date, days=1))}
        elif date_scope == 'to_beginning_of_fiscalyear':
            date_option = {**col_group_options['date'], 'date_to': fields.Date.to_string(fields.Date.add(snapshot_date, days=1))}
        else:
            date_option = {**col_group_options['date'], 'date_to': fields.Date.to_string(snapshot_date)}

        col_group_options = {**col_group_options, 'date': date_option}

        return col_group_options

    @api.model
    def _get_serializable_options(self, options):
        option_keys_to_remove = self._get_option_keys_to_remove_for_snapshot(options)

        serializable_options = {
            key: value
            for key, value in options.items()
            if key not in option_keys_to_remove
        }

        # For options containing multiple elements with a 'selected' flag, we only keep the selected ones, in case some were
        # added between snapshots/evaluations.
        for option_with_select_flag in ('journals', 'aml_ir_filters'):
            serializable_options[option_with_select_flag] = [
                option_part['id']
                for option_part in serializable_options.get(option_with_select_flag, [])
                if option_part['selected']
            ]

        return serializable_options

    @api.model
    def _get_serializable_formulas_dict(self, formulas_dict):
        return {
                formula: sorted(expressions.ids)
                for formula, expressions in formulas_dict.items()
            }

    @api.model
    def _get_option_keys_to_remove_for_snapshot(self, options):
        return {
            'audit', 'available_horizontal_groups', 'available_tax_units', 'available_variants', 'buttons', 'column_groups', 'column_headers',
            'column_percent_comparison', 'columns', 'companies', 'comparison', 'consolidation', 'date', 'display_hierarchy_filter', 'export_mode',
            'filter_date', 'filters', 'forced_companies', 'growth_display', 'has_inactive_sections', 'has_inactive_variants', 'hide_0_lines',
            'hierarchy', 'horizontal_split', 'integer_rounding', 'integer_rounding_enabled', 'journal_groups', 'multi_currency', 'name_journal_group',
            'no_report_reroute', 'order_column', 'owner_column_group', 'readonly_query', 'report_id', 'report_title', 'rounding_unit',
            'rounding_unit_names', 'search_bar', 'sections', 'sections_source_id', 'selected_partner_ids', 'selected_section_id', 'selected_variant_id',
            'show_consolidation', 'show_debug_column', 'show_horizontal_group_total', 'show_last_annotations', 'unfold_all',
            'unfolded_lines', 'user_groups', 'variants_source_id',
        }

    @api.model
    def _snapshot_forbidden(self, options):
        return any(options.get(opt_key) for opt_key in ['partner_categories', 'unreconciled', 'recon_date'])

    def _get_latest_snapshots(self, engine_func_name, engine_version, options, date_scope, formulas_dict, groupby):
        """ Retrieves the most recent snapshot for each company corresponding to these engine parameters.
        """
        if self._snapshot_forbidden(options):
            return self.env['account.report.snapshot']

        report = self.env['account.report'].browse(options['report_id'])
        scoped_date_to = report._get_date_bounds_info(options, date_scope)[1]

        self.env['account.report.snapshot'].flush_model()
        self.env.cr.execute(SQL(
            """
                SELECT DISTINCT ON (company_id)
                    id
                FROM account_report_snapshot
                WHERE
                    report_id = %(report_id)s
                    AND company_id IN %(company_ids)s
                    AND date <= %(date_to)s
                    AND serialized_options = %(serialized_options)s::JSONB
                    AND serialized_formulas_dict = %(serialized_formulas_dict)s::JSONB
                    AND engine_func = %(engine_func)s
                    AND engine_version = %(engine_version)s
                    AND date_scope = %(date_scope)s
                    AND COALESCE(groupby, '') = COALESCE(%(groupby)s, '')
                ORDER BY company_id, date DESC
            """,
            serialized_options=json.dumps(self._get_serializable_options(options)),
            serialized_formulas_dict=json.dumps(self._get_serializable_formulas_dict(formulas_dict)),
            engine_func=engine_func_name,
            engine_version=engine_version,
            date_scope=date_scope,
            report_id=options['report_id'],
            company_ids=tuple(self.env['account.report'].get_report_company_ids(options)),
            date_to=scoped_date_to,
            groupby=groupby,
        ))

        return self.env['account.report.snapshot'].browse(query_res[0] for query_res in self.env.cr.fetchall())

    def _read_result_partitions(self):
        rslt = []
        for record in self:
            json_friendly_result = record.result
            rslt.append({
                self.env['account.report.expression'].browse(int(id_str) for id_str in expression_ids_str.split(',')): formula_res
                for expression_ids_str, formula_res in json_friendly_result.items()
            })

        return rslt

    @api.model
    def _merge_result_partitions(self, result_partitions, result_aggregators):
        def _merge_individual_res_dict(existing_res, new_res):
            for key, new_value in new_res.items():
                aggregator = result_aggregators.get(key)
                existing_value = existing_res[key]

                if not aggregator:
                    raise Exception(self.env._(
                        "Trying to merge engine results values without aggregator: %(new_value)s and %(existing_value)s (key: %(key)s)",
                        new_value=new_value,
                        key=key,
                        existing_value=existing_value,
                    ))

                existing_res[key] = aggregator((existing_value, new_value))

        def grouping_key_sort_key(group_entry):
            # Keys can be mixed types (e.g., None for missing partners, strings, tuples).
            # Bucket them by type to prevent sorting errors.
            grouping_key = group_entry[0]
            if grouping_key is None:
                return (0, '')
            if isinstance(grouping_key, (tuple, list)):
                return (3, tuple(grouping_key_sort_key((sub_key,)) for sub_key in grouping_key))
            if isinstance(grouping_key, str):
                return (2, grouping_key)
            return (1, grouping_key)

        def _merge_sorted_lists(existing_list, new_list):
            # Ordered merge of the two sorted lists, aggregating the entries sharing the same grouping key
            merged_list = []
            existing_deque = deque(existing_list)
            new_deque = deque(new_list)
            while existing_deque and new_deque:
                existing_group_key, existing_group_res = existing_deque[0]
                new_group_key, new_group_res = new_deque[0]

                if existing_group_key == new_group_key:
                    _merge_individual_res_dict(existing_group_res, new_group_res)
                    merged_list.append(existing_deque.popleft())
                    new_deque.popleft()
                elif grouping_key_sort_key(new_deque[0]) < grouping_key_sort_key(existing_deque[0]):
                    merged_list.append(new_deque.popleft())
                else:
                    merged_list.append(existing_deque.popleft())

            merged_list.extend(existing_deque)
            merged_list.extend(new_deque)

            return merged_list

        rslt = {}
        for partition in result_partitions:
            for key, formula_rslt in partition.items():
                if isinstance(formula_rslt, list):
                    formula_rslt.sort(key=grouping_key_sort_key)  # Sort on the grouping keys, to help merging groupby results

                existing_result = rslt.get(key)
                if existing_result:
                    assert isinstance(existing_result, (dict, list))
                    if isinstance(existing_result, dict):
                        assert isinstance(formula_rslt, dict)
                    else:
                        assert isinstance(formula_rslt, list)

                    if isinstance(formula_rslt, list):
                        rslt[key] = _merge_sorted_lists(existing_result, formula_rslt)

                    elif isinstance(formula_rslt, dict):
                        _merge_individual_res_dict(existing_result, formula_rslt)

                    else:
                        raise Exception(self.env._("Wrong engine result format when merging snapshots."))
                else:
                    rslt[key] = formula_rslt

        return rslt
