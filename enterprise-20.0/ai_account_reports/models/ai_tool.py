# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import json
import secrets
from copy import deepcopy

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.json import json_default


class AITool(models.AbstractModel):
    """Read native accounting reports using saved configurations.

    A report_config dict holds uid, action_id, action_report_id,
    allowed_company_ids and the native options dict. action_report_id
    identifies the source action's report; options['report_id'] identifies
    the selected report. allowed_company_ids records the saved selection;
    options['companies'] lists the companies included in the report.
    tool_context['state'] stores this session's configurations and line refs.
    """

    _inherit = 'ai.tool'

    DEFAULT_LIMIT = 60
    MAX_LIMIT = 200
    MAX_REPORT_CONFIGS = 32
    REPORT_CONFIG_KEY = 'accounting_report_configs'
    LINE_REF_KEY = 'accounting_report_line_refs'
    UNAVAILABLE_CATALOG_REPORT_MESSAGE = (
        'The action report {action_report_id} is unavailable or inaccessible. '
        'Use action_report_id from accounting_report_list, not a selected variant or section ID.'
    )

    @api.model
    def _ai_tool_accounting_report_list(self, offset=None, limit=None):
        """Return a dict with a page of accessible reports and pagination.

        Each entry includes report IDs and names, the selected variant/section
        IDs, and whether the report uses a date range.
        """
        offset, limit = self._normalize_page(offset, limit)
        entries = [(report_id, actions[0], options)
                   for report_id, (actions, options) in self._get_report_catalog().items()]
        page, pagination = self._paginate(entries, offset, limit, 'total_reports')
        reports = []
        for report_id, action, options in page:
            report = self.env['account.report'].browse(report_id)
            actual = self.env['account.report'].browse(options['report_id'])
            reports.append({
                'action_report_id': report_id, 'name': report.name,
                **({'alias': action.name} if action.name != report.name else {}),
                'report': {'report_id': options['report_id'], 'name': actual.name},
                **{key: options[key] for key in ('selected_variant_id', 'selected_section_id') if key in options},
                'filter_date_range': actual.filter_date_range})
        return {'reports': reports, 'pagination': pagination}

    @api.model
    def _ai_tool_accounting_report_describe(
        self, tool_context, action_report_id, option_overrides=None,
        offset=None, limit=None,
    ):
        """Describe report choices and lines, then save the configuration.

        Start from a matching browser report or native defaults, then apply
        option_overrides (dict | None). Return a dict with settings, currencies,
        editable option names, a line catalog and report_config_ref (str).
        """
        offset, limit = self._normalize_page(offset, limit)
        entry = self._get_report_catalog(action_report_id).get(action_report_id)
        self._guard(entry, self.UNAVAILABLE_CATALOG_REPORT_MESSAGE.format(action_report_id=action_report_id), AccessError)
        actions, defaults = entry
        current = self._get_current_account_report()
        if current and current['action_report_id'] == action_report_id:
            action_id, options = current['action_id'], current['options']
        else:
            action_id, options = actions[0].id, defaults
        report_config = {
            'uid': self.env.uid, 'action_id': action_id, 'action_report_id': action_report_id,
            'allowed_company_ids': self.env.companies.ids, 'options': options,
        }
        return self._describe_and_save_report_config(
            tool_context, report_config, option_overrides, offset, limit,
        )

    @api.model
    def _ai_tool_accounting_report_select(
        self, tool_context, report_config_ref, choice, option_overrides=None,
        offset=None, limit=None,
    ):
        """Select a variant or section and return the same details as describe.

        choice is {kind: 'variant' | 'section', id: int}, using the saved choices.
        Return a reference for the resulting configuration; the input reference
        keeps its original options.
        """
        offset, limit = self._normalize_page(offset, limit)
        report_config = self._load_report_config(tool_context, report_config_ref)
        kind, choice_id = choice['kind'], choice['id']
        report = self.env['account.report'].browse(report_config['action_report_id'])
        choices_key = 'available_variants' if kind == 'variant' else 'sections'
        available_ids = [item['id'] for item in report_config['options'][choices_key]]
        self._guard(choice_id in available_ids,
                    f'Unavailable {kind} choice {choice_id}. Choose from {choices_key}: {available_ids}.')
        selectors = (
            {'selected_variant_id': choice_id} if kind == 'variant'
            else {'selected_variant_id': report_config['options']['selected_variant_id'], 'selected_section_id': choice_id}
        )
        options = report.get_options({**deepcopy(report_config['options']), **selectors})
        report_config = dict(report_config, options=options)
        return self._describe_and_save_report_config(
            tool_context, report_config, option_overrides, offset, limit, selectors=selectors,
        )

    @api.model
    def _ai_tool_accounting_report_get_values(
        self, tool_context, report_config_ref, columns, line_codes=None,
        offset=None, limit=None,
    ):
        """Return native figures, report settings, warnings and pagination in a dict.

        columns is a nonempty list[str] of expression labels, each including all
        matching periods and groups. line_codes (list[str]) can select static lines.
        Expandable rows include a line_ref (str) for fetching their details.
        Copy options because native rendering can mutate them even in readonly mode.
        """
        self._guard(columns, 'Select at least one column expression label.')
        offset, limit = self._normalize_page(offset, limit)
        report_config = self._load_report_config(tool_context, report_config_ref)
        available_labels = {column['expression_label'] for column in report_config['options']['columns']}
        missing = [label for label in columns if label not in available_labels]
        self._guard(not missing, f'Unavailable columns: {missing}')
        report = self.env['account.report'].browse(report_config['options']['report_id'])
        information = report.get_report_information_readonly(deepcopy(report_config['options']))
        lines = information['lines']
        if line_codes:
            stable = {line.code for line in report.line_ids if line.code}
            by_code = {}
            for line in lines:
                if line.code in line_codes and report._get_markup(line.id) != 'load_more':
                    # Keep the original row when a trailing total repeats its code.
                    by_code.setdefault(line.code, line)
            unavailable = [code for code in line_codes if code not in stable or code not in by_code]
            self._guard(not unavailable, f'Unavailable or uncomputed line_codes: {unavailable}')
            lines = [by_code[code] for code in line_codes]
        result = self._build_report_values_payload(
            report_config, report_config_ref, lines, tool_context,
            columns=columns, offset=offset, limit=limit,
        )
        result['warnings'] = information['warnings']
        return result

    @api.model
    def _ai_tool_accounting_report_expand_line(
        self, tool_context, line_ref, offset=None, limit=None,
    ):
        """Return expanded rows, settings and pagination for line_ref (str) in a dict.

        Reuse the saved options and columns. A load_more reference reloads its
        parent branch, so earlier rows can reappear. Only row warnings are included.
        """
        offset, limit = self._normalize_page(offset, limit)
        ref = (tool_context['state'].get(self.LINE_REF_KEY) or {}).get(line_ref)
        self._guard(ref, 'Stale or mismatched line_ref.')
        report_config = self._load_report_config(tool_context, ref['report_config_ref'])
        report = self.env['account.report'].browse(report_config['options']['report_id'])
        parsed_line_id = report._parse_line_id(ref['line_id'], markup_as_string=True)
        load_more = parsed_line_id[-1][0] == 'load_more'
        line_id = report._build_parent_line_id(parsed_line_id) if load_more else ref['line_id']
        lines = report.get_expanded_lines_readonly(
            deepcopy(report_config['options']), line_id, ref['groupby'], ref['expand_function'],
            ref['horizontal_split_side'], None, ignore_load_more=load_more,
        )
        return self._build_report_values_payload(
            report_config, ref['report_config_ref'], lines, tool_context,
            columns=ref['columns'], offset=offset, limit=limit,
        )

    @api.model
    def _ai_tool_accounting_report_open(self, tool_context, report_config_ref):
        """Open the saved report, or explain why it is already displayed.

        Return a result dict with opened, settings, currencies and the reference.
        When opening is needed, wrap it in {result: dict, client_tool: dict};
        client_tool tells the browser to run the action.
        """
        report_config = self._load_report_config(tool_context, report_config_ref)
        options = report_config['options']
        current = self._get_current_account_report()
        already_displayed = bool(
            current and current['action_report_id'] == report_config['action_report_id'] and current['action_id'] == report_config['action_id']
            and current['report_id'] == options['report_id']
            and current['options'] == json.loads(json.dumps(options, default=json_default, ensure_ascii=False))
        )
        currencies = self.env['res.company'].browse(self.env['account.report'].get_report_company_ids(options)).currency_id
        result = {
            'opened': not already_displayed,
            'report_config': self._get_report_config_for_llm(report_config),
            'currencies': [{'id': c.id, 'name': c.name, 'symbol': c.symbol} for c in currencies],
            'report_config_ref': report_config_ref,
        }
        if already_displayed:
            result['reason'] = 'The exact report and options are already displayed.'
            return result
        action = self.env['ir.actions.client'].browse(report_config['action_id'])._get_action_dict()
        context = ast.literal_eval(action['context'] or '{}')
        action['context'] = dict(context, allowed_company_ids=self.env.companies.ids)
        action['params'] = {
            'options': dict(options, not_reset_journals_filter=True), 'ignore_session': True,
        }
        return {'result': result, 'client_tool': {'name': 'do_action', 'oneway': True, 'params': {'action': action}}}

    def _load_report_config(self, tool_context, report_config_ref):
        """Return the saved configuration dict without rebuilding its options.

        Check the user, company selection (including order) and report access.
        """
        report_config = (tool_context['state'].get(self.REPORT_CONFIG_KEY) or {}).get(report_config_ref)
        self._guard(report_config and report_config['uid'] == self.env.uid, 'Stale or mismatched report_config_ref.')
        self._guard(report_config['allowed_company_ids'] == self.env.companies.ids,
                    'The company selection changed. Describe the report again.')
        if not self.env.user.has_groups('account.group_account_readonly,account.group_account_basic'):
            raise AccessError(self.env._('You must be an accountant to access accounting reports.'))
        self._validate_report_options(report_config['options'])
        return report_config

    def _save_report_config(self, tool_context, report_config):
        """Save a JSON copy in the session and return its string reference.

        Reuse identical copies and move them to the newest position.
        Remove the oldest entry when MAX_REPORT_CONFIGS is exceeded.
        """
        payload = json.loads(json.dumps(report_config, default=json_default, ensure_ascii=False))
        registry = tool_context['state'].setdefault(self.REPORT_CONFIG_KEY, {})
        config_ref = next((ref for ref, saved in registry.items() if saved == payload), None) or secrets.token_urlsafe(18)
        registry.pop(config_ref, None)
        registry[config_ref] = payload
        if len(registry) > self.MAX_REPORT_CONFIGS:
            registry.pop(next(iter(registry)))
        return config_ref

    def _issue_line_ref(self, report_config_ref, line, tool_context, columns):
        """Save a row's expansion details and return a string reference.

        line is an AccountReportLineData object. Keep its report_config_ref and
        column labels for later expansion.
        """
        registry = tool_context['state'].setdefault(self.LINE_REF_KEY, {})
        handle = secrets.token_urlsafe(18)
        registry[handle] = {
            'report_config_ref': report_config_ref, 'columns': columns,
            'line_id': line.id, 'groupby': line.groupby, 'expand_function': line.expand_function,
            'horizontal_split_side': line.horizontal_split_side,
        }
        if len(registry) > 256:
            registry.pop(next(iter(registry)))
        return handle

    def _get_report_catalog(self, requested_report_id=None):
        """Map report IDs to (client action recordset, native options dict).

        Omit requested_report_id to list all reports, or pass an integer ID.
        Unavailable entries are omitted; missing accounting access raises an error.
        Actions are ordered by ID.
        """
        if not self.env.user.has_groups('account.group_account_readonly,account.group_account_basic'):
            raise AccessError(self.env._('You must be an accountant to access accounting reports.'))
        catalog = {}
        for action in self.env['ir.actions.client'].sudo().search([('tag', '=', 'account_report')], order='id'):
            try:
                context = ast.literal_eval(action.context or '{}')
                report_id = context.get('report_id') if isinstance(context, dict) else None
                if not report_id or requested_report_id is not None and report_id != requested_report_id:
                    continue
                report = self.env['account.report'].browse(report_id).exists()
                if (report and report.active and report.has_access('read')
                        and report in report._is_available_for(self.env.companies)):
                    catalog[report_id] = catalog.get(report_id, action.browse()) | action
            except (AccessError, SyntaxError, UserError, ValidationError, ValueError):
                continue
        result = {}
        # A catalog entry remains usable only while its native default can initialize.
        for report_id, actions in catalog.items():
            try:
                defaults = self.env['account.report'].browse(report_id).get_options({})
            except (AccessError, SyntaxError, UserError, ValidationError, ValueError):
                continue
            result[report_id] = (actions, defaults)
        return result

    def _get_current_account_report(self):
        """Return the browser's {action_id, action_report_id, report_id, options}, or None."""
        view = self.env.context.get('current_view_info') or {}
        return view.get('current_account_report')

    @api.model
    def _get_current_account_report_context(self):
        """Return the browser report's IDs, name and options in a dict.

        Return False if no report is open. Include only the options exposed by
        _get_report_options.
        """
        current = self._get_current_account_report()
        if not current:
            return False
        options = current['options']
        return {
            'action_report_id': current['action_report_id'], 'report_id': options['report_id'],
            'report_name': self.env['account.report'].browse(options['report_id']).name,
            'options': self._get_report_options(options),
        }

    def _get_available_report_option_overrides(self, report, options):
        """List the supported option names this report allows the user to change.

        report is an account.report record; options is its native options dict.
        Date is handled separately; variants and sections use the select tool.
        """
        analytic = bool(
            report.filter_analytic_groupby
            and self.env.user.has_group('analytic.group_analytic_accounting')
        )
        return [
            name
            for name, enabled in (
                ('comparison', report.filter_period_comparison),
                ('journals', report.filter_journals or options.get('journals')),
                ('analytic_accounts_groupby', analytic),
                ('partner_ids', report.filter_partner),
                ('partner_categories', report.filter_partner),
                ('account_type', report.filter_account_type not in ('disabled', False)),
                ('all_entries', report.filter_show_draft),
                ('unreconciled', report.filter_unreconciled),
                ('hierarchy', options.get('display_hierarchy_filter')),
                ('tax_unit', report.filter_multi_company == 'tax_units'),
                ('selected_horizontal_group_id', options.get('available_horizontal_groups')),
            )
            if enabled
        ]

    def _validate_report_options(self, options):
        # Validate the native company scope before accessing the effective report.
        companies = self.env['res.company'].browse(
            self.env['account.report'].get_report_company_ids(options)
        )
        if companies[:1] != self.env.company or companies - self.env.companies:
            raise ValidationError(self.env._('The report engine returned an invalid company scope.'))
        report = self.env['account.report'].browse(options.get('report_id')).exists()
        if not (report and report.active and report.has_access('read')
                and report in report._is_available_for(companies)):
            raise AccessError(self.env._('Unavailable report.'))

    def _apply_report_option_overrides(self, report_config, option_overrides, selectors=None):
        """Apply overrides with native get_options and return a report_config dict."""
        # The schema inserts None for omitted options; preserve explicit False and [].
        changes = {name: value for name, value in (option_overrides or {}).items() if value is not None}
        if not changes:
            return report_config
        options = report_config['options']
        report = self.env['account.report'].browse(options['report_id'])
        unsupported = changes.keys() - {'date', *self._get_available_report_option_overrides(report, options)}
        self._guard(not unsupported, f'Unsupported report option overrides: {sorted(unsupported)}.')
        for name in ('date', 'comparison'):
            if name in changes:
                value = changes[name] = {key: item for key, item in changes[name].items() if item is not None}
                dates = {'date_from', 'date_to'} & value.keys()
                for key in dates:
                    fields.Date.to_date(value[key])
                self._guard(dates != {'date_from', 'date_to'} or value['date_from'] <= value['date_to'], 'Invalid dates.')
        if 'date' in changes:
            date = changes['date']
            self._guard(date['period_type'] == 'custom' or 'date_from' not in date, 'Invalid date form.')
            self._guard(date['period_type'] != 'custom' or ('date_from' in date) == report.filter_date_range,
                        'Unavailable date form.')
        if 'comparison' in changes:
            comparison = changes['comparison']
            custom = comparison['filter'] == 'custom'
            count = comparison.get('number_period')
            self._guard(
                custom == ({'date_from', 'date_to'} <= comparison.keys())
                and (count is None or count <= 5)
                and (not custom or count in (None, 1))
                and (comparison['filter'] != 'no_comparison' or count is None),
                'Invalid comparison form.',
            )
        if 'journals' in changes:
            available_ids = {journal['id'] for journal in options['journals']}
            unavailable_ids = {journal['id'] for journal in changes['journals'] if journal['selected']} - available_ids
            self._guard(not unavailable_ids, f'Unavailable selected journal IDs: {sorted(unavailable_ids)}. '
                        'Choose journals from report_config.options.journals.')
        if 'partner_categories' in changes:
            ids = changes['partner_categories']
            categories = self.env['res.partner.category'].with_context(active_test=False)
            if set(categories.search([('id', 'in', ids)]).ids) != set(ids):
                raise AccessError(self.env._('Invalid or inaccessible partner_categories.'))
        options = self.env['account.report'].browse(report_config['action_report_id']).get_options(
            {**deepcopy(options), **(selectors or {}), **changes},
        )
        return dict(report_config, options=options)

    def _describe_and_save_report_config(
        self, tool_context, report_config, option_overrides, offset, limit, selectors=None,
    ):
        """Apply overrides, save the configuration and return its description dict.

        selectors (dict | None) holds variant/section IDs that must remain selected
        after native get_options runs. The result includes report_config_ref (str).
        """
        report_config = self._apply_report_option_overrides(report_config, option_overrides, selectors)
        options = report_config['options']
        self._validate_report_options(options)
        for name, choice_id in (selectors or {}).items():
            self._guard(options.get(name) == choice_id,
                        f'Native reporting did not apply {name}={choice_id}; returned {options.get(name)}.')
        report = self.env['account.report'].browse(options['report_id'])
        lines = [{'code': line.code, 'name': line.name, 'hierarchy_level': line.hierarchy_level}
                 for line in report.line_ids if line.code]
        lines, pagination = self._paginate(lines, offset, limit, 'total_lines')
        currencies = self.env['res.company'].browse(report.get_report_company_ids(options)).currency_id
        result = {
            'report_config': self._get_report_config_for_llm(report_config),
            'currencies': [{'id': c.id, 'name': c.name, 'symbol': c.symbol} for c in currencies],
            'available_option_overrides': self._get_available_report_option_overrides(report, options),
            'line_catalog': {'items': lines, 'pagination': pagination},
        }
        result['report_config_ref'] = self._save_report_config(tool_context, report_config)
        return result

    def _build_report_values_payload(
        self, report_config, report_config_ref, lines, tool_context, *, columns, offset, limit,
    ):
        """Format native report rows into a dict for the LLM.

        lines contains AccountReportLineData objects. Keep the requested column
        labels across all groups, paginate rows and add expansion references.
        Include settings, currencies, column groups and any row warnings.
        Figures and column definitions remain unchanged.
        """
        options = report_config['options']
        report = self.env['account.report'].browse(options['report_id'])
        lines_page = []
        for line in lines[offset:offset + limit]:
            line_columns = [{
                'expression_label': column.expression_label, 'column_group_index': column.column_group_index,
                'no_format': column.no_format, 'name': column.name,
            } for column in line.columns or [] if column.expression_label in columns]
            markup = report._get_markup(line.id)
            expandable = bool(line.expand_function and (line.unfoldable or markup == 'load_more'))
            lines_page.append({
                'code': line.code, 'name': line.name, 'level': line.level,
                'row_type': markup if markup in ('total', 'load_more') else 'data', 'unfoldable': line.unfoldable,
                'line_ref': self._issue_line_ref(report_config_ref, line, tool_context, columns) if expandable else None,
                'columns': line_columns})
            if warning_text := (line.custom or {}).get('warning_text'):
                lines_page[-1]['warning_text'] = warning_text
        next_offset = offset + len(lines_page)
        currencies = self.env['res.company'].browse(report.get_report_company_ids(options)).currency_id
        return {
            'report_config': self._get_report_config_for_llm(report_config),
            'currencies': [{'id': c.id, 'name': c.name, 'symbol': c.symbol} for c in currencies],
            'report_config_ref': report_config_ref,
            'column_groups': options['column_groups'], 'lines': lines_page,
            'pagination': {'offset': offset, 'limit': limit, 'total_lines': len(lines),
                           'next_offset': next_offset if next_offset < len(lines) else None},
        }

    def _get_report_config_for_llm(self, report_config):
        """Return {action_report_id: int, options: dict} for the LLM.

        Keep only the options exposed by _get_report_options. Other saved fields
        stay internal.
        """
        return {
            'action_report_id': report_config['action_report_id'],
            'options': self._get_report_options(report_config['options']),
        }

    def _get_report_options(self, options):
        """Return the report settings and metadata exposed to the LLM as a dict.

        Keep native keys and values unchanged. This subset cannot replace the
        full options used to render or open the report.
        """
        option_keys = {
            'report_id', 'companies', 'columns', 'date', 'comparison', 'all_entries', 'unreconciled', 'hierarchy',
            'journals', 'account_type', 'analytic_accounts_groupby', 'partner_ids', 'partner_categories', 'aging_based_on',
            'tax_unit', 'selected_horizontal_group_id', 'selected_variant_id', 'selected_section_id',
            'available_variants', 'sections', 'available_tax_units', 'available_horizontal_groups', 'filter_date',
        }
        return {key: value for key, value in options.items() if key in option_keys}

    def _normalize_page(self, offset, limit):
        offset = 0 if offset is None else offset
        limit = self.DEFAULT_LIMIT if limit is None else limit
        self._guard(limit <= self.MAX_LIMIT, f'Page limit cannot exceed {self.MAX_LIMIT}.')
        return offset, limit

    def _paginate(self, values, offset, limit, total_key):
        """Return (page, pagination dict) from a list or recordset.

        total_key names the total count; next_offset is None on the last page.
        """
        page = values[offset:offset + limit]
        next_offset = offset + len(page)
        return page, {'offset': offset, 'limit': limit, total_key: len(values),
                      'next_offset': next_offset if next_offset < len(values) else None}

    def _guard(self, condition, message, error=ValidationError):
        if not condition:
            raise error(message)
