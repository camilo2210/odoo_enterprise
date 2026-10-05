# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from collections import Counter

from markupsafe import Markup

from odoo import Command, fields, models
from odoo.tools import html2plaintext

from odoo.addons.ai.utils.ai_utils import make_confirmation_request_preview


class AIAuditTool(models.AbstractModel):
    _inherit = 'ai.tool'

    def _audit_file(self, audit_id):
        """Return the audit working file (account.return) for audit_id (int).

        Check access and require its companies and main company to match the
        current selection.
        """
        audit = self.env['account.return'].browse(audit_id).exists()
        self._guard(audit, 'Working file not found.')
        audit.check_access('read')
        self._guard(audit.type_id.category == 'audit', 'Select an audit working file, not a tax return.')
        # Native audit fields use the file's companies, independently of the environment.
        self._guard(audit.company_id == self.env.company
                    and set(audit.company_ids.ids) == set(self.env.companies.ids),
                    "Select the working file's companies and main company in Odoo's company selector.")
        return audit

    def _audit_context_result(self):
        """Return {'audit_context': dict} for the working file in context, or {}.

        Include its ID, companies, dates and a reminder that ordinary searches
        still use their own domains.
        """
        if not (audit_id := self.env.context.get('working_file_id')):
            return {}
        audit = self._audit_file(audit_id)
        return {'audit_context': {
            'working_file_id': audit.id,
            'company_ids': audit.company_ids.ids,
            'date_from': fields.Date.to_string(audit.date_from),
            'date_to': fields.Date.to_string(audit.date_to),
            'notice': 'Audit-computed fields use this working file. Ordinary record searches still follow '
                      'their supplied domains. Clear the working file before unrelated queries with '
                      'accounting_audit_set_working_file(audit_id=null).',
        }}

    def _ai_tool_search(self, model_name, domain="", fields=None, offset=0, limit=None, order=None):
        """Return the search result dict with any active audit context in response."""
        audit_context = self._audit_context_result()
        result = super()._ai_tool_search(model_name, domain, fields, offset, limit, order)
        result['response'].update(audit_context)
        return result

    def _ai_tool_read_group(self, model_name, domain, groupby=None, aggregates=None, having="", offset=0, limit=None, order=None):
        """Return the grouped result dict with any active audit context in response."""
        audit_context = self._audit_context_result()
        result = super()._ai_tool_read_group(model_name, domain, groupby, aggregates, having, offset, limit, order)
        result['response'].update(audit_context)
        return result

    def _ai_tool_accounting_audit_set_working_file(self, tool_context, audit_id):
        """Select audit_id (int | None) in this session; None clears the selection.

        Save it in request_context and return {audit_context: dict | None}.
        The company selection is unchanged.
        """
        result = self.with_context(working_file_id=audit_id)._audit_context_result()
        session = self.env['ai.session'].sudo().browse(tool_context['session_id'])
        context = dict(session.request_context or {})
        if audit_id:
            context['working_file_id'] = audit_id
        else:
            context.pop('working_file_id', None)
        session.request_context = context
        return result or {'audit_context': None}

    def _audit_cycle_checks(self, audit, cycle):
        """Return an account.return.check recordset for a cycle code in audit.

        Use 'other' for checks without a cycle. Raise if no checks match.
        """
        checks = audit.check_ids.filtered(lambda check: (check.cycle_id.code or 'other') == cycle)
        self._guard(checks, 'Unknown or empty cycle. Copy a cycle code from accounting_audit_get_checks.')
        return checks

    def _audit_progress(self, audit):
        """Return working-file details and check counts for each cycle in a dict.

        Counts and completion flags reflect saved statuses and refresh flags;
        they do not establish that evidence was investigated.
        """
        def counts(checks):
            results = Counter(checks.mapped('result'))
            return {
                'total': len(checks), 'pending': results['todo'], 'anomalies': results['anomaly'],
                'reviewed': results['reviewed'] + results['supervised'],
                'manual_pending': len(checks.filtered(lambda c: c.type == 'file' and c.result == 'todo')),
                'checks_pending': len(checks.filtered(
                    lambda c: c.type != 'file' and (c.refresh_result or c.result == 'todo'))),
            }
        checks = audit.check_ids
        cycles = [{
            'code': cycle.code, 'name': cycle.name,
            **counts(checks.filtered(lambda c: c.cycle_id == cycle)),
        } for cycle in checks.cycle_id.sorted()]
        if other := checks.filtered(lambda c: not c.cycle_id):
            cycles.append({'code': 'other', 'name': 'Other', **counts(other)})
        totals = counts(checks)
        return {
            'audit_id': audit.id, 'name': audit.name,
            'url': f'/odoo/action-account_reports.action_view_account_audit_checks?active_id={audit.id}',
            'company_ids': audit.company_ids.ids, 'companies': audit.company_ids.mapped('display_name'),
            'date_from': fields.Date.to_string(audit.date_from), 'date_to': fields.Date.to_string(audit.date_to),
            'cycles': cycles, 'totals': totals,
            'remaining_cycles': [c['code'] for c in cycles if c['checks_pending']],
            'all_checks_investigated': not totals['checks_pending'],
            'all_requirements_reviewed': not totals['pending'] and not totals['anomalies'] and not totals['checks_pending'],
            'formally_completed': audit.is_completed,
        }

    def _audit_confirmation(self, tool_context, body):
        """Request confirmation and return True, or return False to proceed.

        Put the confirmation request in tool_context['user_input_request'].
        After approval, reject writes if the company selection changed.
        """
        if not tool_context.get('tool_request_confirmed'):
            tool_context['user_input_request'] = make_confirmation_request_preview(self.env, body)
            return True
        session = self.env['ai.session'].sudo().browse(tool_context['session_id'])
        self._guard(session.request_context['allowed_company_ids'] == self.env.companies.ids,
                    'The company selection changed. Request this operation again.')
        return False

    def _ai_tool_accounting_audit_create(self, tool_context, date_from, date_to):
        """Create a working file for the requested dates after confirmation.

        date_from and date_to are YYYY-MM-DD strings. Require one selected
        company without parents or branches. Return a progress dict, or None
        with user_input_request set when approval is needed.
        """
        self._guard(len(self.env.companies) == 1,
                    'Select one company in Odoo before creating an audit working file.')
        start, end = fields.Date.to_date(date_from), fields.Date.to_date(date_to)
        self._guard(start and end and start <= end, 'Provide a valid start date on or before the end date.')
        self.env['account.return'].check_access('create')
        company = self.env.company
        # REVIEW: What's this guard for?
        # Native creation may traverse branch trees; require a single company here.
        self._guard(not company.parent_id and not company.child_ids,
                    'Create this branched-company working file in Accounting, then provide its audit_id.')
        values = {'company_id': company.id, 'category': 'audit', 'date_from': start, 'date_to': end}
        wizard_model = self.env['account.return.creation.wizard']
        wizard_model.check_access('create')
        wizard = wizard_model.new(values)
        return_type = wizard.return_type_id._origin
        self._guard(return_type, 'No native audit return type is available for this company.')
        values['return_type_id'] = return_type.id
        # The template is literal; Markup formatting escapes the company name and dates.
        if self._audit_confirmation(tool_context, Markup(
            '<p>Create an audit working file for <strong>%s</strong>, %s to %s, '
            'with the native configured checks?</p>'
        ) % (company.display_name, start, end)):
            return
        wizard = wizard_model.create(values)
        self._guard(wizard.return_type_id, 'No native audit return type is available for this company.')
        action = wizard.action_create_manual_account_returns()
        audit_id = action['params']['next_action']['context']['active_id']
        audit = self._audit_file(audit_id)
        self._guard(audit.date_from == start and audit.date_to == end,
                    'Native creation changed the requested scope. Create the working file in Accounting.')
        return self._audit_progress(audit)

    def _ai_tool_accounting_audit_get_checks(self, audit_id, cycle=None, offset=None, limit=None):
        """Return working-file progress and a page of check details in a dict.

        Include instructions, notes, status, action availability and attachment IDs.
        cycle (str | None) limits the page to one cycle; omit it for all checks.
        """
        audit = self._audit_file(audit_id)
        checks = self._audit_cycle_checks(audit, cycle) if cycle else audit.check_ids
        offset, limit = self._normalize_page(offset, limit)
        page, pagination = self._paginate(checks, offset, limit, 'total_checks')
        return {
            **self._audit_progress(audit), 'selected_cycle': cycle,
            'checks': [{
                'code': check.code, 'name': check.name, 'message': html2plaintext(check.message or ''),
                'type': check.type, 'cycle': check.cycle_id.code or 'other', 'result': check.result,
                'notes': check.notes or '', 'native_records_count_hint': check.records_count,
                'has_action': bool(check.action), 'attachment_ids': check.attachment_ids.ids,
            } for check in page], 'pagination': pagination,
        }

    def _audit_action(self, check):
        """Return the native action dict for a check, if one is available.

        Resolve known server actions through native methods. Return other server
        actions without running them. No view is opened.
        """
        action = check.with_context(working_file_id=check.return_id.id).action_review()
        if not action or action.get('type') != 'ir.actions.server':
            return action
        context = action.get('context') or {}
        check = check.with_context(**{**context, 'working_file_id': check.return_id.id})
        if action.get('id') == self.env.ref('account_reports.action_audit_report').id:
            return check.action_audit_report(check.return_id.id, context.get('action_xml_id'))
        if action.get('id') == self.env.ref('account_reports.action_audit_custom_target').id and context.get('target') in (
            'depreciation_schedule', 'inventory_valuation', 'fleet', 'documents', 'invoices_to_be_issued',
        ):
            return check.action_audit_custom_target(check.return_id.id, context.get('target'))
        if action.get('id') == self.env.ref(
            'account_reports.action_server_open_view_account_return_with_additional_params',
        ).id:
            return check.return_id.action_open_tax_return_view(
                context.get('sub_action_domain'), context.get('sub_action_context'),
            )
        return action  # Unknown executable actions are never run.

    def _ai_tool_accounting_audit_get_check_action_detail(self, audit_id, check_code):
        """Describe a check's action without opening it or fetching evidence records.

        Use audit_id (int) and check_code (str) to find the check. Return a dict
        with action_detail and, for window actions, search and main view XML.
        If no action exists, include the check instructions and attachment IDs.
        """
        audit = self._audit_file(audit_id)
        check = audit.check_ids.filtered(lambda c: c.code == check_code)
        self._guard(check, 'Unknown check code. Read accounting_audit_get_checks first.')
        action = self._audit_action(check)
        # The tool dispatcher executes a top-level 'action' as navigation.
        result = {
            'audit_id': audit.id, 'check_code': check.code,
            'company_ids': audit.company_ids.ids, 'action_detail': action,
        }
        if not action:
            return {**result, 'hint': html2plaintext(check.message or ''),
                    'attachment_ids': check.attachment_ids.ids}
        if action['type'] != 'ir.actions.act_window':
            return result
        self._check_agent_model_access(action['res_model'])
        context = action.get('context') or {}
        context = literal_eval(context) if isinstance(context, str) else context
        model = self.env[action['res_model']].with_context(
            **{**context, 'allowed_company_ids': self.env.companies.ids},
        )
        search_view_id = (action.get('search_view_id') or (False,))[0]
        result['views'] = {
            view_type: model.get_view(view_id, view_type)['arch']
            for view_id, view_type in [(search_view_id, 'search'), action['views'][0]]
        }
        return result

    def _ai_tool_accounting_audit_update_checks(self, tool_context, audit_id, cycle, updates):
        """Save a cycle's findings after confirmation and refresh its active view.

        updates is a list of dicts with check_code, notes and result.
        Return {result: dict, client_tool: dict}, or None with user_input_request
        set while waiting for approval. result includes progress and updated codes.
        """
        audit = self._audit_file(audit_id)
        checks = self._audit_cycle_checks(audit, cycle)
        self._guard(updates and len(updates) <= 100, 'Provide between 1 and 100 findings for one cycle.')
        by_code = {check.code: check for check in checks}
        self._guard(len({u['check_code'] for u in updates}) == len(updates), 'Duplicate check codes.')
        checks.check_access('write')
        self._guard(not audit.state, 'This working file has already been reviewed.')
        for update in updates:
            check = by_code.get(update['check_code'])
            self._guard(check and check.type != 'file', 'Every finding must target a non-file check in this cycle.')
            self._guard(update['notes'].strip(), 'Each finding needs non-blank notes.')
        # Check names, results and notes are escaped by the literal Markup template's formatting.
        rows = Markup('').join(Markup('<li><strong>%s — %s</strong><pre>%s</pre></li>') % (
            by_code[u['check_code']].name, u['result'], u['notes'],
        ) for u in updates)
        # Names are escaped here; rows were already built with escaping-aware formatting.
        if self._audit_confirmation(tool_context, Markup('<p>Save findings for %s, cycle %s?</p><ul>%s</ul>') % (
            audit.name, cycle, rows,
        )):
            return
        # Native check tracking shares the parent return and field name.
        # Finalize each change so a batch keeps separate, accurate entries.
        audit._track_finalize()
        for update in updates:
            # Saving AI findings is not human approval of those findings.
            by_code[update['check_code']].write({
                'notes': update['notes'], 'result': update['result'],
                'approver_ids': [Command.clear()],
            })
            audit._track_finalize()
        result = {'updated_codes': [u['check_code'] for u in updates], **self._audit_progress(audit)}
        action = {
            'type': 'ir.actions.client', 'tag': 'action_return_refresh',
            'params': {'return_ids': audit.ids},
        }
        return {'result': result, 'client_tool': {'name': 'do_action', 'oneway': True, 'params': {'action': action}}}
