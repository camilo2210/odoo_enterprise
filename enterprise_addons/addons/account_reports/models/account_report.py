# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import bisect
import contextlib
import datetime
import io
import itertools
import json
import logging
import re
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key
from itertools import chain, groupby
import markupsafe
from dateutil.relativedelta import relativedelta
from PIL import ImageFont

from ..utils.report_data_objects import AccountReportColumnData, AccountReportLineData, AccountReportColumnFormatParamsData, AccountReportLineChatterData
from odoo import _, api, fields, models
from odoo.addons.web.controllers.utils import clean_action
from odoo.addons.account.models.account_report import ACCOUNT_CODES_ENGINE_SPLIT_REGEX, ACCOUNT_CODES_ENGINE_TERM_REGEX, CROSS_REPORT_REGEX
from odoo.addons.account_reports.models.account_report_snapshot import snapshotable_engine
from odoo.exceptions import AccessError, RedirectWarning, UserError, ValidationError
from odoo.fields import Command, Domain
from odoo.models import Query, get_public_method
from odoo.tools import (
    BinaryBytes,
    LazyTranslate,
    SQL,
    file_path,
    float_compare,
    float_is_zero,
    float_repr,
    float_round,
    format_date,
    formatLang,
    get_lang,
    html2plaintext,
    parse_version,
)
from odoo.tools.mail import html_to_inner_content
from odoo.tools.safe_eval import expr_eval
from odoo.release import version

_lt = LazyTranslate(__name__)
_logger = logging.getLogger(__name__)

ACCOUNT_CODES_ENGINE_TAG_ID_PREFIX_REGEX = re.compile(r"tag\(((?P<id>\d+)|(?P<ref>\w+\.\w+))\)")
AGG_ENGINE_TERM_SEPARATOR_REGEX = re.compile(r"(?<!\de)[+-]|[ ()/*]")
AGG_ENGINE_BOUND_CRITERIUM_REGEX = re.compile(r"^(?P<criterium>\w+)\((?P<line_code>\w+)[.](?P<expr_label>\w+),[ ]*(?P<bound_params>.*)\)$")

NUMBER_FIGURE_TYPES = ('float', 'integer', 'monetary', 'percentage')

LINE_ID_HIERARCHY_DELIMITER = '|'

CURRENCIES_USING_LAKH = {'AFN', 'BDT', 'INR', 'MMK', 'NPR', 'PKR', 'LKR'}

UNDISTR_LINE_NAME = _lt("Result Brought Forward")


class AccountReportAnnotation(models.Model):
    _name = 'account.report.annotation'
    _description = 'Account Report Annotation'

    # This field is a OneToOne to a mail.message.
    message_id = fields.Many2one('mail.message', string="Message", required=True)
    date = fields.Date(help="Date considered as annotated by the annotation.", required=True)


class AccountReport(models.Model):
    _inherit = 'account.report'

    display_custom_groupby_warning = fields.Boolean(compute='_compute_display_custom_groupby_warning')

    horizontal_group_ids = fields.Many2many(string="Horizontal Groups", comodel_name='account.report.horizontal.group')
    return_type_ids = fields.One2many(string="Return Types", comodel_name='account.return.type', inverse_name='report_id')
    snapshot_ids = fields.One2many(string="Snapshots", comodel_name='account.report.snapshot', inverse_name='report_id')

    # Those fields allow case-by-case fine-tuning of the engine, for custom reports.
    custom_handler_model_id = fields.Many2one(string='Custom Handler Model', comodel_name='ir.model')
    custom_handler_model_name = fields.Char(string='Custom Handler Model Name', related='custom_handler_model_id.model')

    @api.model
    def _get_available_pdf_engines(self):
        report_type_field = self.env['ir.actions.report']._fields.get('report_type')
        if not report_type_field:
            return [('html', 'HTML')]

        selection = report_type_field._description_selection(self.env)
        engines = {
            engine_name
            for value, _label in selection
            if isinstance(value, str) and value.startswith('qweb-pdf-')
            if (engine_name := value.removeprefix('qweb-pdf-'))
        }
        return [('html', 'HTML')] + [(name, name) for name in sorted(engines)]

    force_pdf_engine = fields.Selection(
        selection=_get_available_pdf_engines,
        string='Force PDF Engine',
        help=(
            "PDF rendering engine used to generate this report when exporting to PDF. "
            "Some engines may ignore headers/footers."
        ),
    )

    def _get_pdf_engine_name(self, options=None):
        """Resolve the PDF engine name for this report.

        Priority:
        1) explicit override in options/context (useful for tests/debug)
        2) per-report configuration (wkhtmltopdf / paper-muncher)
        3) config's default (ir.config_parameter.report.pdf_engine_default)
        4) fallback: wkhtmltopdf
        """
        self.ensure_one()
        options = options or {}

        return (
            options.get('pdf_engine')
            or self.env.context.get('pdf_engine')
            or self.force_pdf_engine
            or self.env['ir.actions.report']._get_pdf_engine()
        )

    # Account Coverage Report
    is_account_coverage_report_available = fields.Boolean(compute='_compute_is_account_coverage_report_available')

    # Fields used for send reports by cron
    send_and_print_values = fields.Json(copy=False)

    # Account Audit Status
    allow_account_audit_status_on_lines = fields.Boolean(string="Allow Account Audit Status On Lines",
        compute=lambda x: x._compute_report_option_filter('allow_account_audit_status_on_lines'), readonly=False,
        precompute=True, store=True, depends=['root_report_id'])

    def _compute_display_custom_groupby_warning(self):
        for report in self:
            report.display_custom_groupby_warning = report.get_external_id()[report.id] and report.user_groupby != report.groupby

    @api.constrains('custom_handler_model_id')
    def _validate_custom_handler_model(self):
        for report in self:
            if report.custom_handler_model_id:
                custom_handler_model = self.env.registry['account.report.custom.handler']
                current_model = self.env[report.custom_handler_model_name]
                if not isinstance(current_model, custom_handler_model):
                    raise ValidationError(_(
                        "Field 'Custom Handler Model' can only reference records inheriting from [%s].",
                        custom_handler_model._name
                    ))

    @api.constrains('groupby', 'user_groupby')
    def _validate_groupby(self):
        for report in self:
            report._check_groupby_fields(report.user_groupby)
            report._check_groupby_fields(report.groupby)

    def unlink(self):
        for report in self:
            action, menuitem = report._get_existing_menuitem()
            menuitem.unlink()
            action.unlink()
        return super().unlink()

    def write(self, vals):
        if 'active' in vals:
            reports = {r.id: r.name for r in self}
            actions = self.env['ir.actions.client'].sudo() \
                .search([('name', 'in', list(reports.values())), ('tag', '=', 'account_report')]) \
                .filtered(lambda act: (ast.literal_eval(act.context).get('report_id'), act.name) in reports.items())
            self.env['ir.ui.menu'].sudo() \
                .search([
                    ('active', '=', not vals['active']),
                    ('action', 'in', [f'ir.actions.client,{action.id}' for action in actions]),
                ])\
                .active = vals['active']

        rslt = super().write(vals)

        # If the configuration of the report changed and it requires snapshots ; they might need to be refreshed
        if any(self.mapped('enable_snapshots')):
            self.env.ref('account_reports.ir_cron_create_snapshots')._trigger()

        return rslt

    @api.model_create_multi
    def create(self, vals_list):
        reports = super().create(vals_list)

        reports_by_impacted_field = {}
        for report, impacted_fields in zip(reports, vals_list):
            for field_name in impacted_fields:
                reports_by_impacted_field.setdefault(field_name, self.env['account.report'])
                reports_by_impacted_field[field_name] += report

        if root_annual_statements := self.env.ref('account_reports.annual_statements', raise_if_not_found=False):
            asr_section_reports = reports.filtered_domain(self._asr_sections_domain(root_annual_statements))

            if asr_section_reports:
                # When the report needs to be added to the annual statement, the computation of some of its filters
                # might be skipped (because it's linked to a single composite report). Make sure we compute those
                # filters once before setting the link to the composite report.
                for name, field in asr_section_reports._fields.items():
                    if field._depends and 'section_main_report_ids' in field._depends and field.store:
                        # We then need to recompute the fields on the reports not setting it in the create (all the filters are also editable)
                        reports_to_recompute = reports - reports_by_impacted_field.get(name, self.env['account.report'])
                        if reports_to_recompute:
                            self.env.add_to_compute(field, reports_to_recompute)
                            reports_to_recompute._recompute_field(field)

            asr_section_reports._link_annual_statements(root_annual_statements)

        if any(reports.mapped('enable_snapshots')):
            self.env.ref('account_reports.ir_cron_create_snapshots')._trigger()

        target_reports = [
            self.env.ref('account_reports.balance_sheet', raise_if_not_found=False),
            self.env.ref('account_reports.profit_and_loss', raise_if_not_found=False),
            self.env.ref('account_reports.cash_flow_report', raise_if_not_found=False),
        ]
        if horizontal_group_ledger := self.env.ref('account_reports.horizontal_group_ledger', raise_if_not_found=False):
            horizontal_group_ledger.report_ids += reports.filtered(lambda r: r.root_report_id in target_reports)

        return reports

    def _load_records(self, data_list, update=False):
        reports = super()._load_records(data_list, update=update)

        all_companies = self.env['res.company'].sudo().search([])
        for company in all_companies:
            if not company.vat_disabled:
                continue
            company._toggle_account_reports_on_vat_disabled(reports)

        return reports

    def action_reset_custom_groupby(self):
        self.ensure_one()
        self.user_groupby = self.groupby

    def action_open_snapshots(self):
        self.ensure_one()
        return self.snapshot_ids._get_records_action(views=[(False, 'list')], name=_("Snapshots"))

    def _asr_sections_domain(self, root_annual_statements):
        """
        The domain returned by this function is used to filter which reports
        should be a section of an annual statements report
        """
        return [
            ('root_report_id', 'in', root_annual_statements.section_report_ids.ids),
            ('availability_condition', '!=', 'always'),  # the report has to be localized
        ]

    def _link_annual_statements(self, root_annual_statements):
        for asr_section_report in self:
            annual_statements = self.env['account.report'].search([
                ('root_report_id', '=', root_annual_statements.id),
                ('country_id', '=', asr_section_report.country_id.id),
                ('chart_template', '=', asr_section_report.chart_template),
            ])
            if not annual_statements:
                annual_statements = self.env['account.report'].create({
                    'name': _("Annual Statements"),
                    'root_report_id': root_annual_statements.id,
                    'country_id': asr_section_report.country_id.id,
                    'use_sections': True,
                    'chart_template': asr_section_report.chart_template,
                    'availability_condition': asr_section_report.availability_condition,
                    'section_report_ids': [Command.set(root_annual_statements.section_report_ids.ids)],
                })

            annual_statements.section_report_ids -= asr_section_report.root_report_id

            if asr_section_report.use_sections:
                annual_statements.section_report_ids += asr_section_report.section_report_ids
            else:
                annual_statements.section_report_ids += asr_section_report
                asr_section_report.sequence = asr_section_report.root_report_id.sequence

    ####################################################
    # CRON
    ####################################################

    @api.model
    def _cron_account_report_send(self, job_count=10):
        """ Handle Send & Print async processing.
        :param job_count: maximum number of jobs to process if specified.
        """
        to_process = self.env['account.report'].search(
            [('send_and_print_values', '!=', False)],
        )
        if not to_process:
            return

        processed_count = 0
        need_retrigger = False

        for report in to_process:
            if need_retrigger:
                break
            send_and_print_vals = report.send_and_print_values
            report_partner_ids = send_and_print_vals.get('report_options', {}).get('partner_ids', [])
            need_retrigger = processed_count + len(report_partner_ids) > job_count
            partner_ids = report_partner_ids[:job_count - processed_count]
            company_id = send_and_print_vals['report_options']['companies'][0]['id']
            existing_partner_ids = set(self.env['res.partner'].browse(partner_ids).exists().ids)
            for partner_id in partner_ids:
                if partner_id in existing_partner_ids:
                    options = {
                        **send_and_print_vals['report_options'],
                        'partner_ids': [partner_id],
                    }
                    self.env['account.report.send']._process_send_and_print(report=report.with_context(allowed_company_ids=(company_id,)), options=options)
                    processed_count += 1
                report_partner_ids.remove(partner_id)
            if report_partner_ids:
                send_and_print_vals['report_options']['partner_ids'] = report_partner_ids
                report.send_and_print_values = send_and_print_vals
            else:
                report.send_and_print_values = False

        if need_retrigger:
            self.env.ref('account_reports.ir_cron_account_report_send')._trigger()

    ####################################################
    # MENU MANAGEMENT
    ####################################################

    def _get_existing_menuitem(self):
        self.ensure_one()
        action = self.env['ir.actions.client']\
            .search([('name', '=', self.name), ('tag', '=', 'account_report')])\
            .filtered(lambda act: ast.literal_eval(act.context).get('report_id') == self.id)
        menuitem = self.env['ir.ui.menu']\
            .with_context({'active_test': False})\
            .search([('action', '=', f'ir.actions.client,{action.id}')])
        return action, menuitem

    def _create_menu_item_for_report(self):
        """ Adds a default menu item for this report. This is called by an action on the report, for reports created manually by the user.
        """
        self.ensure_one()

        action, menuitem = self._get_existing_menuitem()

        if menuitem:
            raise UserError(_("This report already has a menuitem."))

        if not action:
            action = self.env['ir.actions.client'].create({
                'name': self.name,
                'tag': 'account_report',
                'context': {'report_id': self.id},
            })

        self.env['ir.ui.menu'].create({
            'name': self.name,
            'parent_id': self.env['ir.model.data']._xmlid_to_res_id('account.menu_finance_reports'),
            'action': f'ir.actions.client,{action.id}',
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    ####################################################
    # OPTIONS: journals
    ####################################################

    def _get_filter_journals(self, options, additional_domain=None):
        return self.env['account.journal'].with_context(active_test=False).search([
                *self.env['account.journal']._check_company_domain(self.get_report_company_ids(options)),
                *(additional_domain or []),
            ], order="company_id, name")

    def _get_journal_groups(self):
        return self.env['account.journal.group'].search([('included_journal_ids.company_id', 'in', self.env.companies.ids)], order='sequence, id')

    def _init_options_journals(self, options, previous_options, additional_journals_domain=None):
        def option_journal(journal, company_id, unfolded, visible, selected=False):
            return {
                'id': journal.id,
                'name': journal.display_name,
                'selected': selected,
                'company_id': company_id.id,
                'company_name': company_id.display_name,
                'title': f"{journal.name} - {journal.code}",
                'type': journal.type,
                'unfolded': unfolded,
                'visible': visible,
                'group_id': journal.journal_group_id.id,
            }

        def option_journal_group(journal_group, selected=False):
            return {
                'id': journal_group.id or 'local_gaap',
                'name': journal_group.name,
                'selected': selected,
                'title': journal_group.display_name,
                'journals': journal_group.included_journal_ids.ids,
                'journal_types': list(set(journal_group.included_journal_ids.mapped('type')))
            }

        previous_journals = previous_options.get('journals', [])
        previous_journal_group_action = previous_options.get('__journal_group_action', {})

        all_journals = self._get_filter_journals(options, additional_domain=additional_journals_domain)
        all_journal_groups = self._get_journal_groups()

        if not self.filter_journals and not all_journal_groups:
            return

        options['journals'] = []
        options['journal_groups'] = []

        # First time opening the report, and make sure it's not specifically stated that we should not reset the filter
        is_opening_report = previous_options.get('is_opening_report')  # key from JS controller when report is being opened
        # a key to prevent the reset of the journals filter even when is_opening_report is True
        can_reset_journals_filter = not previous_options.get('not_reset_journals_filter')

        gaap_group = self.env['account.journal.group'].browse(['local_gaap'])

        if is_opening_report and can_reset_journals_filter:
            selected_journals_ids = set(gaap_group.included_journal_ids.ids)
        else:
            selected_journals_ids = {journal['id'] for journal in previous_journals if journal.get('selected')}

        if all_journal_groups and gaap_group.included_journal_ids:
            all_journal_groups = gaap_group + all_journal_groups

        # 1. Handle journal group selection : if all journals of a group are selected, then select the group
        selected_journal_groups = {
            group
            for group in all_journal_groups
            if selected_journals_ids >= set(group.included_journal_ids.ids)
        }

        # 2. Handle the journal_group_action
        if previous_journal_group_action and all_journal_groups:
            actions = {
                "add": lambda id_set, id: id_set.add(id),
                "remove": lambda id_set, id: id_set.discard(id),
            }
            action_group = next(group for group in all_journal_groups if group["id"] == previous_journal_group_action['id'])
            actions[previous_journal_group_action['action']](selected_journal_groups, action_group)
            for journal in action_group.included_journal_ids:
                actions[previous_journal_group_action['action']](selected_journals_ids, journal._origin.id)

        # 3. Build group options
        if all_journal_groups:
            for group in all_journal_groups:
                selected = group in selected_journal_groups
                options['journal_groups'].append(option_journal_group(group, selected=selected))

        # If no explicit ledgers and all journals are selected, we prefer they appear unselected
        deselect_all_journal = selected_journals_ids == set(all_journals.ids) and not all_journal_groups
        # 4. Build journal options
        for journal in all_journals:
            if len(self.env.companies) == 1 and not all_journal_groups:
                unfolded = True
            else:
                unfolded = False if is_opening_report else next(
                    (previous_journal.get('unfolded') for previous_journal in previous_journals if previous_journal.get('id') == journal.id), False)
            visible = unfolded and self.filter_journals
            selected = journal.id in selected_journals_ids and not deselect_all_journal
            options['journals'].append(option_journal(journal, journal.company_id, unfolded, visible, selected=selected))

    def _init_options_audit(self, options, previous_options):

        if 'working_file_export_checks' in previous_options:
            options['working_file_export_checks'] = previous_options['working_file_export_checks']

        if not self.allow_account_audit_status_on_lines:
            return

        main_company = self._get_sender_company_for_export(options)

        domain = Domain([
            ('return_type_category', '=', 'audit'),
            ('company_id', '=', main_company.id),
            ('date_to', '=', options['date']['date_to']),
        ])

        if options['date']['date_from']:
            domain &= Domain('date_from', '=', options['date']['date_from'])

        audit_return = self.env['account.return'].search_read(domain, limit=1, fields=['id'])

        options.setdefault('audit', {})
        options['audit']['id'] = audit_return[0]['id'] if len(audit_return) > 0 else False

    def _init_options_journals_names(self, options, previous_options, additional_journals_domain=None):
        # 1. Get the names of the journals or journal groups selected
        all_journals, is_local_gaap_selected, names_company, names_journal_group, names_journal = self._get_journals_list_of_names(options, additional_journals_domain)
        if all_journals:
            names_to_display = [_('All Journals')] if self.filter_journals else [_('All Ledgers')]
        else:
            names_to_display = names_journal_group + names_journal
            if not is_local_gaap_selected:
                names_to_display = names_company + names_to_display
        # 2. Abbreviate the name
        max_nb_journals_displayed = 5
        nb_remaining = len(names_to_display) - max_nb_journals_displayed
        displayed_names = ', '.join(names_to_display[:max_nb_journals_displayed])
        if nb_remaining == 1:
            options['name_journal_group'] = _("%(names)s and one other", names=displayed_names)
        elif nb_remaining > 1:
            options['name_journal_group'] = _("%(names)s and %(remaining)s others", names=displayed_names, remaining=nb_remaining)
        else:
            options['name_journal_group'] = displayed_names

    def _get_journals_list_of_names(self, options, additional_journals_domain=None):

        all_journals = self._get_filter_journals(options, additional_journals_domain)
        company2journals = all_journals.grouped('company_id')

        journal_selected_ids = [journal.get('id') for journal in options.get('journals', []) if journal.get('selected')]
        journal_group_selected_ids = [journal_group.get('id') for journal_group in options.get('journal_groups', []) if journal_group.get('selected')]

        is_local_gaap_selected = 'local_gaap' in journal_group_selected_ids

        selected_journals = self.env['account.journal'].browse(journal_selected_ids)
        selected_journal_groups = self.env['account.journal.group'].browse(journal_group_selected_ids)

        names_journal_group = selected_journal_groups.mapped('display_name')
        journals_to_display = selected_journals - selected_journal_groups.included_journal_ids
        names_company = []
        for company, company_journals in company2journals.items():
            company_gaap_journals = company_journals.filtered(lambda r: not r.journal_group_id)
            if company_gaap_journals and selected_journals >= company_gaap_journals:
                names_company.append(company.display_name)
                journals_to_display -= company_gaap_journals
        names_journal = journals_to_display.mapped('display_name')

        are_all_journal_selected = not selected_journals or selected_journals == all_journals

        return are_all_journal_selected, is_local_gaap_selected, names_company, names_journal_group, names_journal

    @api.model
    def _get_options_journals(self, options):
        selected_journals = [
            journal for journal in options.get('journals', [])
            if journal['selected']
        ]
        if not selected_journals:
            # If no journal is specifically selected, we actually want to select them all.
            # This is needed, because some reports will not use ALL available journals and filter by type.
            # Without getting them from the options, we will use them all, which is wrong.
            selected_journals = [
                journal for journal in options.get('journals', [])
            ]
        return selected_journals

    @api.model
    def _get_options_journals_domain(self, options):
        # Make sure to return an empty array when nothing selected to handle archived journals.
        selected_journals = self._get_options_journals(options)
        return Domain('journal_id', 'in', [j['id'] for j in selected_journals]) if selected_journals else Domain.TRUE

    # ####################################################
    # OPTIONS: USER DEFINED FILTERS ON AML
    ####################################################
    def _init_options_aml_ir_filters(self, options, previous_options):
        options['aml_ir_filters'] = []
        if not self.filter_aml_ir_filters:
            return

        ir_filters = self.env['ir.filters'].search([('model_id', '=', 'account.move.line')])
        if not ir_filters:
            return

        aml_ir_filters = [{'id': x.id, 'name': x.name, 'selected': False} for x in ir_filters]
        previous_options_aml_ir_filters = previous_options.get('aml_ir_filters', [])
        previous_options_filters_map = {filter_item['id']: filter_item for filter_item in previous_options_aml_ir_filters}

        for filter_item in aml_ir_filters:
            if filter_item['id'] in previous_options_filters_map:
                filter_item['selected'] = previous_options_filters_map[filter_item['id']]['selected']

        options['aml_ir_filters'] = aml_ir_filters

    @api.model
    def _get_options_aml_ir_filters(self, options):
        selected_filters_ids = [
            filter_item['id']
            for filter_item in options.get('aml_ir_filters', [])
            if filter_item['selected']
        ]

        if not selected_filters_ids:
            return Domain.TRUE

        selected_ir_filters = self.env['ir.filters'].browse(selected_filters_ids)
        return Domain.OR(filter_record._get_eval_domain() for filter_record in selected_ir_filters)

    ####################################################
    # OPTIONS: date + comparison
    ####################################################

    @api.model
    def _compute_period_range(self, date, months_per_period, start_day, start_month):
        """ Returns the start and end dates of a period based on the given date and the period type. """
        # Offsets the date back from start_day amount of day - 1 so we can compute months periods aligned to the start and end of months
        aligned_date = date + relativedelta(days=-(start_day - 1))

        year = aligned_date.year
        month_offset = aligned_date.month - start_month
        period_number = (month_offset // months_per_period) + 1

        # If the date is before the start date and start month of this year, this mean we are in the previous period
        # So the initial_date should be one year before and the period_number should be computed in reverse because month_offset is negative
        if date < datetime.date(date.year, start_month, start_day):
            year -= 1
            period_number = ((12 + month_offset) // months_per_period) + 1

        month_delta = period_number * months_per_period

        # We need to work with offsets because it handles automatically the end of months (28, 29, 30, 31)
        # -1 because the first day is already counted and -1 because the first day of the next period must not be in this range
        end_date = datetime.date(year, start_month, 1) + relativedelta(months=month_delta, days=start_day - 2)
        start_date = datetime.date(year, start_month, 1) + relativedelta(months=month_delta - months_per_period, day=start_day)

        return start_date, end_date

    @api.model
    def _build_date_dict(self, options, date_from, date_to, period_type='custom', label=None, mode=None, fallback_from=None):
        """ Build the date dictionary for report options.

        :param dict options: Current report options.
        :param date date_from: Start date (can be None for 'single' mode).
        :param date date_to: End date (must be set).
        :param string period_type: Type of period used to calculate dates.
        :param string label: Optional string to override the default generated label.
        :param string mode: Optional 'single' or 'range' override; defaults to report mode.
        :param string fallback_from: Indicates if the current period_type is a fallback from another.
        :return: A date filter dictionary ready to be injected into report options.
        """
        if not date_to:
            raise UserError(self.env._("'date_to' must be set when generating the report date options."))

        if mode:
            range_mode = mode == 'range'
        else:
            range_mode = options['filter_date']['range_mode']

        if range_mode and not date_from:
            raise UserError(self.env._("'date_from' must be set when generating the report date options in range mode."))

        filter_dict = options['filter_date']['filters'].get(period_type, {})
        start_day = filter_dict.get('start_day', 1)
        start_month = filter_dict.get('start_month', 1)
        if date_from and isinstance(date_from, str):
            date_from = fields.Date.to_date(date_from)
        if isinstance(date_to, str):
            date_to = fields.Date.to_date(date_to)

        date_dict = {
            'string': label if label else self._build_date_label(options, range_mode, date_from, date_to, start_day, start_month),
            'date_from': fields.Date.to_string(date_from) if range_mode else None,
            'date_to': fields.Date.to_string(date_to),
            'period_type': period_type,
        }

        if fallback_from:
            date_dict['fallback_from'] = fallback_from

        return date_dict

    def _infer_period_type_from_dates(self, options, date_from, date_to):
        def match_date(dt_from, dt_to):
            if date_from:
                return (dt_from, dt_to) == (date_from, date_to)
            else:
                return dt_to == date_to

        fy_dates = self.env.company.compute_fiscalyear_dates(date_to)
        fiscal_year_match = match_date(fy_dates['date_from'], fy_dates['date_to'])
        calendar_year_match = match_date(fields.Date.start_of(date_to, "year"), fields.Date.end_of(date_to, "year"))

        if (fiscal_year_match and self.use_fiscal_periods) or (calendar_year_match and not self.use_fiscal_periods):
            return 'year'

        if match_date(*self._get_period_dates(options, date_to, 'month')):
            return 'month'

        if match_date(*self._get_period_dates(options, date_to, 'quarter')):
            return 'quarter'

        if not date_from and fields.Date.context_today(self) == date_to:
            return 'today'

        for filter_key, filter_dict in options['filter_date']['filters'].items():
            custom_ranges = filter_dict.get('custom_ranges')
            custom_range_match = self._find_custom_range_in_period(custom_ranges, date_to) if custom_ranges else None
            if custom_range_match and match_date(custom_range_match[0], custom_range_match[1]):
                return filter_key

        return 'custom'

    @api.model
    def _build_date_label(self, options, range_mode, date_from, date_to, start_day=1, start_month=1, complete=False):
        def build_date_label_generic():
            if date_from == fields.Date.start_of(date_from, 'month') and date_to == fields.Date.end_of(date_to, 'month'):
                if date_from.month == date_to.month and date_from.year == date_to.year:
                    return format_date(self.env, date_to, date_format="MMM yyyy")
                return self.env._("%(date_from)s - %(date_to)s", date_from=format_date(self.env, date_from, date_format="MMM yyyy"), date_to=format_date(self.env, date_to, date_format="MMM yyyy"))

            return self.env._("%(date_from)s - %(date_to)s", date_from=format_date(self.env, date_from), date_to=format_date(self.env, date_to))

        if not range_mode or not date_from:
            return self.env._("As of %(date_to)s", date_to=format_date(self.env, date_to))

        if start_day != 1 or start_month != 1 or complete:
            return build_date_label_generic()

        inferred_period_type = self._infer_period_type_from_dates(options, date_from, date_to)
        match inferred_period_type:
            case 'month':
                return format_date(self.env, date_to, date_format='MMM yyyy')
            case 'quarter':
                return self.env._(
                    "%(date_from)s - %(date_to)s",
                    date_from=format_date(self.env, date_from, date_format='MMM'),
                    date_to=format_date(self.env, date_to, date_format='MMM yyyy')
                )
            case 'year':
                return date_to.strftime('%Y')
            case _:
                return build_date_label_generic()

    @api.model
    def _get_period_dates(self, options, date_in_period, period_type):
        """ Helper function to build date_from and date_to from a single date and a period type. """
        if period_type in ('today', 'custom'):
            period_type = 'year'

        filter_dict = options['filter_date']['filters'].get(period_type)
        if not filter_dict:
            raise UserError(self.env._("Cannot build period from unknown period type."))

        custom_ranges = filter_dict.get('custom_ranges')
        custom_range_match = self._find_custom_range_in_period(custom_ranges, date_in_period) if custom_ranges else None
        if custom_range_match:
            return fields.Date.to_date(custom_range_match[0]), fields.Date.to_date(custom_range_match[1])

        start_day = filter_dict['start_day']
        start_month = filter_dict['start_month']
        months_per_period = filter_dict['months_per_period']

        return self._compute_period_range(date_in_period, months_per_period, start_day, start_month)

    @api.model
    def _find_custom_range_in_period(self, custom_ranges, date):
        """  Helper function that returns the custom date range containing the given date. """
        for range_start, range_end, range_name in custom_ranges:
            if fields.Date.to_date(range_start) <= date <= fields.Date.to_date(range_end):
                return range_start, range_end, range_name
        return False

    @api.model
    def _get_shifted_dates_period(self, options, relative_period, side):
        """ Get the previous or next period based on relative_period.

        :param dict relative_period: The relative date dictionary used as the base period.
        :param number side: Direction of the shift: -1 for previous, 1 for next.
        :return: A date options dictionary containing:
            * date_from * date_to * label * filter
        """
        if side not in (-1, 1):
            raise UserError(self.env._("Argument 'side' is not valid. Either choose -1 or 1 to indicate respectively the previous or next period."))

        filter_date = options['filter_date']
        range_mode = filter_date['range_mode']
        date_to = fields.Date.to_date(relative_period['date_to'])

        relative_period_type = relative_period.get('period_type')
        if relative_period_type in ('custom', 'today'):
            relative_period_type = 'year'

        filter_dict = filter_date['filters'].get(relative_period_type, filter_date['filters'].get('month'))
        period_type = filter_dict.get('key', 'month')
        months_per_period = filter_dict.get('months_per_period', 1)
        start_day = filter_dict.get('start_day', 1)
        start_month = filter_dict.get('start_month', 1)

        if not range_mode and side == -1:
            date_from, date_to = self._get_period_dates(options, date_to, period_type)
        else:
            date_from = fields.Date.to_date(relative_period['date_from'])

        reference_date = date_from if side == -1 else date_to
        reference_date = reference_date + relativedelta(days=side)

        custom_ranges = filter_dict.get('custom_ranges')
        custom_range_match = self._find_custom_range_in_period(custom_ranges, reference_date) if custom_ranges else None
        if custom_range_match:
            return self._build_date_dict(options, custom_range_match[0], custom_range_match[1], period_type, custom_range_match[2], fallback_from=relative_period.get('fallback_from'))

        date_from, date_to = self._compute_period_range(reference_date, months_per_period, start_day, start_month)
        return self._build_date_dict(options, date_from, date_to, period_type, fallback_from=relative_period.get('fallback_from'))

    @api.model
    def _get_dates_previous_year(self, options, period_vals):
        """Shift the period to the previous year.
        :param options:     The report options.
        :param period_vals: A dictionary generated by the _build_date_dict method.
        :return:            A dictionary containing:
            * date_from * date_to * label * filter *
        """
        period_type = period_vals.get('period_type', 'custom')

        date_from = period_vals['date_from']
        if date_from:
            date_from = fields.Date.to_date(date_from) - relativedelta(years=1)

        date_to = fields.Date.to_date(period_vals['date_to'])
        date_to = date_to - relativedelta(years=1)

        return self._build_date_dict(options, date_from, date_to, period_type, fallback_from=period_vals.get('fallback_from'))

    def _init_options_filter_date(self, options, previous_options):
        """ Generates the date filters options:

        range_mode : bool                               True = range mode, False = single date mode.
        fiscal_year_report : bool                       True if report is based on fiscal year.
        default_opening_date : str or datetime.date     The default opening date for the report.
        filters : dict                                  Keys are filter types ('year', 'month', ...).
            key : str                                       Internal key of the period type.
            label : str                                     Translated display label.
            months_per_period : int                         Number of months from date_from to date_to.
            start_day : int                                 Day offset when period starts.
            start_month : int                               Month offset when period starts
            sequence : int                                  Display order of the filter.
            fallback : str or None                          Fallback filter key if applicable.
        """
        def fill_custom_ranges_gap(custom_ranges, start_day, start_month, months_per_period):
            """ Given a custom ranges list, fill all the gaps so that all the custom ranges are aligned accordingly
            to the period parameters (start_month, start_day, range). """
            def add_filler(start, end):
                name = self._build_date_label(options, range_mode, start, end, start_day, start_month, complete=True)
                filled_custom_ranges.append((start, end, name))

            if not custom_ranges:
                return custom_ranges

            filled_custom_ranges = []
            next_start_date = False
            for custom_range_start, custom_range_end, custom_range_name in custom_ranges:
                # Compute normal period of the current range
                current_period_range = self._compute_period_range(custom_range_start, months_per_period, start_day, start_month)

                if not next_start_date:
                    # Fill the initial next_start_date
                    next_start_date = current_period_range[0]
                elif next_start_date < current_period_range[0]:
                    # Gap over two normal periods. We need to fill the gap from previous period
                    new_filling_range_start = next_start_date
                    new_filling_range_end = current_period_range[0] - relativedelta(days=1)
                    add_filler(new_filling_range_start, new_filling_range_end)
                    next_start_date = current_period_range[0]

                if next_start_date != custom_range_start:
                    # Gap between last range and this one
                    new_filling_range_start = next_start_date
                    new_filling_range_end = custom_range_start - relativedelta(days=1)
                    add_filler(new_filling_range_start, new_filling_range_end)

                # Add the current custom range and set the next start date
                filled_custom_ranges.append((custom_range_start, custom_range_end, custom_range_name))
                next_start_date = custom_range_end + relativedelta(days=1)

            # The last custom range might not end at a normal period end so we need to handle that at the end
            last_custom_range = filled_custom_ranges[-1]
            current_period_range = self._compute_period_range(last_custom_range[1], months_per_period, start_day, start_month)
            if last_custom_range[1] != current_period_range[1]:
                new_filling_range_start = last_custom_range[1] + relativedelta(days=1)
                new_filling_range_end = current_period_range[1]
                add_filler(new_filling_range_start, new_filling_range_end)

            return filled_custom_ranges

        range_mode = self.filter_date_range
        use_fiscal_periods = self.use_fiscal_periods
        filter_date = {
            'range_mode': range_mode,
            'default_opening_date': self.default_opening_date_filter,
            'filters': {},
        }

        filter_date['filters']['month'] = {
            'key': 'month',
            'label': self.env._("Month") if range_mode else self.env._("End of Month"),
            'months_per_period': 1,
            'start_day': 1,
            'start_month': 1,
            'sequence': 10,
            'fallback': False,
        }

        filter_date['filters']['quarter'] = {
            'key': 'quarter',
            'label': self.env._("Quarter") if range_mode else self.env._("End of Quarter"),
            'months_per_period': 3,
            'start_day': 1,
            'start_month': 1,
            'sequence': 20,
            'fallback': False,
        }

        if use_fiscal_periods:
            main_company = self.env.company
            last_month, last_day = int(main_company.fiscalyear_last_month), int(main_company.fiscalyear_last_day)
            default_year = 2024 if (last_month == 2 and last_day == 29) else 2025
            fy_end = datetime.date(month=last_month, day=last_day, year=default_year)  # year doesn't matter here.
            fy_start = fy_end + relativedelta(days=1)

            filter_date['filters']['quarter']['start_day'] = fy_start.day
            filter_date['filters']['quarter']['start_month'] = fy_start.month
            filter_date['filters']['month']['start_day'] = fy_start.day
            filter_date['filters']['month']['start_month'] = fy_start.month

            # Fetch custom ranges and fill the gaps
            custom_ranges = [
                (fiscal_year.date_from, fiscal_year.date_to, fiscal_year.name)
                for fiscal_year in self.env['account.fiscal.year'].search([('company_id', '=', main_company.id)], order="date_from")
            ]
            custom_ranges = fill_custom_ranges_gap(custom_ranges, fy_start.day, fy_start.month, 12)

            filter_date['filters']['year'] = {
                'key': 'year',
                'label': self.env._("Fiscal Year") if range_mode else self.env._("End of Fiscal Year"),
                # We use the default range, start_date and start_month to compute fy when there is no custom range
                'months_per_period': 12,
                'start_day': fy_start.day,
                'start_month': fy_start.month,
                'sequence': 30,
                'fallback': False,
                'custom_ranges': custom_ranges,
            }
        else:
            filter_date['filters']['year'] = {
                'key': 'year',
                'label': self.env._("Year") if range_mode else self.env._("End of Year"),
                'months_per_period': 12,
                'start_day': 1,
                'start_month': 1,
                'sequence': 30,
                'fallback': False,
            }

        if return_periodicity_options := options.get('return_periodicity'):
            periodicity = return_periodicity_options['periodicity']
            months_per_period = return_periodicity_options['months_per_period']
            start_day = return_periodicity_options['start_day']
            start_month = return_periodicity_options['start_month']

            return_period = {
                'key': 'return_period',
                'label': self.env._("Return"),
                'months_per_period': months_per_period,
                'start_day': start_day,
                'start_month': start_month,
                'sequence': 50,
            }
            filter_date['filters']['return_period'] = return_period

            is_yearly_period = (periodicity == 'fiscalyear' and use_fiscal_periods) or (periodicity == 'year' and not use_fiscal_periods)
            if is_yearly_period:
                return_period['fallback'] = 'year'

            else:
                # Fallback to the first existing filter that matches the return period configuration
                return_period['fallback'] = next((
                    key for key, filter_dict in filter_date['filters'].items()
                    if key != 'return_period' and
                       filter_dict.get('start_day') == start_day and
                       filter_dict.get('start_month') == start_month and
                       filter_dict.get('months_per_period') == months_per_period
                ), False)

        if not range_mode:
            filter_date['filters']['today'] = {
                'key': 'today',
                'label': self.env._("Today"),
                'sequence': 0,
            }

        options['filter_date'] = filter_date

    def _init_options_date(self, options, previous_options):
        """ Initialize the 'date' options key.

        :param options:             The current report options to build.
        :param previous_options:    The previous options coming from another report.
        """
        date = previous_options.get('date', {})
        filter_date = options['filter_date']
        range_mode = filter_date['range_mode']
        period_type = date.get('period_type')
        today = fields.Date.context_today(self)
        date_to = date.get('date_to')
        date_to = fields.Date.to_date(date_to) if date_to else None
        date_from = fields.Date.to_date(date['date_from']) if date.get('date_from') else None
        shift = 0
        fallback_from = date.get('fallback_from')
        provided_date_to = bool(date_to)

        if not period_type and date_to and (not range_mode or date_from):
            inferred_period_type = self._infer_period_type_from_dates(options, date_from, date_to)
            period_type = inferred_period_type
            fallback_from = 'custom' if inferred_period_type != 'custom' else None

        # If period_type is custom, try to infer another period_type if possible
        elif period_type == 'custom':
            if range_mode and not date_from:
                date_from = self.env.company.compute_fiscalyear_dates(date_to)['date_from']
            if not date_to:
                date_to = today
            period_type = self._infer_period_type_from_dates(options, date_from, date_to)
            if period_type != 'custom':
                fallback_from = 'custom'

        if period_type == 'custom':
            options['date'] = self._build_date_dict(options, date_from, date_to, period_type, fallback_from=fallback_from)
            return

        if not date_to:
            date_to = today

        if not period_type:
            default_opening_date = date.get('default_opening_date', filter_date['default_opening_date'])

            if 'return_period' in default_opening_date and not filter_date['filters'].get('return_period'):
                period_type = 'month'
            elif default_opening_date.startswith('this_'):
                period_type = default_opening_date.replace('this_', '')
            elif default_opening_date == 'today':
                period_type = 'today'
            else:  # previous_ or next_
                shift = 1 if default_opening_date.startswith('next_') else -1
                if default_opening_date.endswith('_month'):
                    period_type = 'month'
                elif default_opening_date.endswith('_quarter'):
                    period_type = 'quarter'
                elif default_opening_date.endswith('_year'):
                    period_type = 'year'
                elif default_opening_date.endswith('_return_period'):
                    period_type = 'return_period'
                else:
                    raise UserError(self.env._("An unknown opening date method was provided: %(default_opening_date)s", default_opening_date=default_opening_date))

        if period_type == 'today':
            if range_mode:
                fiscal_year_start = self.env.company.compute_fiscalyear_dates(date_to)['date_from']
                options['date'] = self._build_date_dict(options, fiscal_year_start, date_to, 'custom', fallback_from=fallback_from)
            else:
                options['date'] = self._build_date_dict(options, None, date_to, period_type, fallback_from=fallback_from)
            return

        date_filter = filter_date['filters'].get(period_type)

        if not date_filter:
            raise UserError(self.env._("filter '%(filter)s' is not present in the available filters.", filter=period_type))

        custom_ranges = date_filter.get('custom_ranges')

        if period_type == 'year':
            latest_date_range = False
            if custom_ranges:
                for start, end, name in custom_ranges:
                    if end.year == date_to.year and end >= date_to and start <= date_to and (not latest_date_range or latest_date_range[1] < end):
                        latest_date_range = (start, end, name)

            if latest_date_range:
                options['date'] = self._build_date_dict(options, latest_date_range[0], latest_date_range[1], period_type, latest_date_range[2], fallback_from=fallback_from)
            else:
                new_date_from, new_date_to = self._get_period_dates(options, date_to, period_type)
                if new_date_to.year > date_to.year and provided_date_to:
                    # If the date_to from the previous company, gives a period that span a year after, we shift back.
                    new_date_from, new_date_to = self._get_period_dates(options, new_date_from + relativedelta(days=-1), period_type)
                options['date'] = self._build_date_dict(options, new_date_from, new_date_to, period_type, fallback_from=fallback_from)
        else:
            custom_range_match = self._find_custom_range_in_period(custom_ranges, date_to) if custom_ranges else None
            if custom_range_match:
                options['date'] = self._build_date_dict(options, custom_range_match[0], custom_range_match[1], period_type, custom_range_match[2], fallback_from=fallback_from)
            else:
                date_from, date_to = self._get_period_dates(options, date_to, period_type)
                options['date'] = self._build_date_dict(options, date_from, date_to, period_type, fallback_from=fallback_from)

            if period_type == 'return_period' and (fallback := date_filter.get('fallback')):
                options['date']['period_type'] = fallback

        if shift != 0:
            options['date'] = self._get_shifted_dates_period(options, options['date'], shift)

    def _init_options_return_periodicity(self, options, previous_options):
        if (previous_options.get('return_periodicity')
            and previous_options['return_periodicity'].get('return_type_id')
            and previous_options['return_periodicity'].get('report_id') in (False, self.id, options['sections_source_id'])):
            options['return_periodicity'] = {
                **previous_options['return_periodicity'],
                'report_id': self.id,
            }
        elif len(return_type := self.env['account.report'].browse(options['sections_source_id']).return_type_ids) == 1 or 'selected_return_type_id' in previous_options:
            if len(return_type) > 1:
                return_type = self.env['account.return.type'].browse(previous_options['selected_return_type_id'])

            main_company = self.env.company
            start_day, start_month = return_type._get_start_date_elements(main_company)
            options['return_periodicity'] = {
                'periodicity': return_type._get_periodicity(main_company),
                'months_per_period': return_type._get_periodicity_months_delay(main_company),
                'start_day': start_day,
                'start_month': start_month,
                'return_type_id': return_type.id,
                'report_id': self.id,
            }

    def _init_options_comparison(self, options, previous_options):
        """ Initialize the 'comparison' options key.

        This filter must be loaded after the 'date' filter.

        :param options:             The current report options to build.
        :param previous_options:    The previous options coming from another report.
        """
        if not self.filter_period_comparison:
            return

        previous_comparison = previous_options.get('comparison', {})
        previous_filter = previous_comparison.get('filter')

        period_order = previous_comparison.get('period_order') or 'descending'
        if previous_filter == 'custom':
            # Try to adapt the previous 'custom' filter.
            date_from = previous_comparison.get('date_from')
            date_to = previous_comparison.get('date_to')
            number_period = 1
            options_filter = 'custom'

        else:
            # Use the 'date' options.
            date_to = min(options['date']['date_to'], fields.Date.to_string(fields.Date.context_today(self)))
            date_from = fields.Date.to_string(
                self.env.company.compute_fiscalyear_dates(fields.Date.to_date(date_to))['date_from']
            )
            number_period = max(previous_comparison.get('number_period', 1) or 0, 0)

            if previous_filter == 'report_line':
                if self.filter_line_comparison and len(self.column_ids) == 1 and previous_comparison.get('base_report_line', {}).get('id') in self.line_ids.ids:
                    options_filter = previous_filter
                else:
                    options_filter = 'no_comparison'
            else:
                options_filter = number_period and previous_filter or 'no_comparison'

        options['comparison'] = {
            'filter': options_filter,
            'number_period': number_period,
            'date_from': date_from,
            'date_to': date_to,
            'periods': [],
            'period_order': period_order,
        }

        if options_filter == 'report_line':
            options['comparison']['base_report_line'] = previous_comparison['base_report_line']

        date_from_obj = fields.Date.to_date(date_from)
        date_to_obj = fields.Date.to_date(date_to)

        if options_filter == 'custom':
            options['comparison']['periods'].append(self._build_date_dict(
                options,
                date_from_obj,
                date_to_obj,
                self._infer_period_type_from_dates(options, date_from_obj, date_to_obj),
            ))
        elif options_filter in ('previous_period', 'same_last_year'):
            previous_period = options['date']
            for _i in range(number_period):
                if options_filter == 'previous_period':
                    period_vals = self._get_shifted_dates_period(options, previous_period, -1)
                elif options_filter == 'same_last_year':
                    period_vals = self._get_dates_previous_year(options, previous_period)
                options['comparison']['periods'].append(period_vals)
                previous_period = period_vals

    def _init_options_column_percent_comparison(self, options, previous_options):
        if self.filter_growth_comparison and len(options['columns']) == 2 and len(options.get('comparison', {}).get('periods', [])) == 1:
            options['column_percent_comparison'] = 'growth'

        if (
                options.get('display_analytic_groupby')
                and len(options.get('analytic_plans_groupby', [])) == 1
                and not options.get('analytic_accounts')
                and not options.get('comparison', {}).get('periods', [])
                and len(options['columns']) == 2
        ):
            options['column_percent_comparison'] = 'analytic_coverage'

        if self.filter_budgets and any(budget['selected'] for budget in options.get('budgets', [])):
            options['column_percent_comparison'] = 'budget'

        options['growth_display'] = 'amount' if previous_options.get('growth_display') == 'amount' else 'percent'
        # Toggling growth_display only changes anything when a growth comparison column actually renders,
        # which requires one column per column group (Trial Balance and similar render Debit/Credit per group).
        column_groups = options.get('column_groups') or []
        options['hide_growth_display_filter'] = bool(column_groups) and len(options['columns']) != len(column_groups)

        if options.get('comparison', {}).get('filter') == 'report_line':
            options['column_percent_comparison'] = 'report_line'
            # report_line percent is a line-ratio, not a growth column, so hide the toggle.
            options['hide_growth_display_filter'] = True

    def _get_options_date_domain(self, options, date_scope):
        date_from, date_to = self._get_date_bounds_info(options, date_scope)

        scope_domain = Domain('date', '<=', date_to)
        if date_from:
            scope_domain &= Domain('date', '>=', date_from)

        return scope_domain

    def _get_date_bounds_info(self, options, date_scope):
        # Default values (the ones from 'strict_range')
        date_to = options['date']['date_to']
        date_from = options['date']['date_from'] if options['filter_date']['range_mode'] else None

        if date_scope == 'from_beginning':
            date_from = None

        elif date_scope == 'to_beginning_of_period':
            date_tmp = fields.Date.from_string(date_from or date_to) - relativedelta(days=1)
            date_to = date_tmp.strftime('%Y-%m-%d')
            date_from = None

        elif date_scope == 'from_fiscalyear':
            date_tmp = fields.Date.from_string(date_to)
            date_tmp = self.env.company.compute_fiscalyear_dates(date_tmp)['date_from']
            date_from = date_tmp.strftime('%Y-%m-%d')

        elif date_scope == 'to_beginning_of_fiscalyear':
            date_tmp = fields.Date.from_string(date_to)
            date_tmp = self.env.company.compute_fiscalyear_dates(date_tmp)['date_from'] - relativedelta(days=1)
            date_to = date_tmp.strftime('%Y-%m-%d')
            date_from = None

        elif date_scope == 'previous_return_period':
            return_types = self.return_type_ids  # Might be empty ; if so, we'll call the functions on an empty recordset and fallback to company periodicity

            if len(return_types) > 1:
                if len(set(return_types.mapped('deadline_periodicity'))) > 1:
                    raise UserError(_(
                        "'%s' date scope cannot be evaluated for a report used by multiple return types using different periodicities.",
                        dict(self.env['account.report.expression']._fields['date_scope']._description_selection(self.env))['previous_return_period'],
                    ))
                return_types = return_types[0]

            current_period_start, _current_period_end = return_types._get_period_boundaries(self.env.company, fields.Date.from_string(options['date']['date_from']))
            eve_of_period_start = current_period_start - relativedelta(days=1)
            date_from, date_to = return_types._get_period_boundaries(self.env.company, eve_of_period_start)

        return date_from, date_to

    ####################################################
    # OPTIONS: partners
    ####################################################

    def _init_options_partner(self, options, previous_options):
        if not self.filter_partner:
            return

        options['partner'] = True
        previous_partner_ids = previous_options.get('partner_ids') or []
        options['partner_categories'] = previous_options.get('partner_categories') or []

        selected_partner_ids = [int(partner) for partner in previous_partner_ids]
        # search instead of browse so that record rules apply and filter out the ones the user does not have access to
        selected_partners = selected_partner_ids and self.env['res.partner'].with_context(active_test=False).search([('id', 'in', selected_partner_ids)]) or self.env['res.partner']
        options['selected_partner_ids'] = selected_partners.mapped('display_name')
        options['partner_ids'] = selected_partners.ids

        selected_partner_category_ids = [int(category) for category in options['partner_categories']]
        selected_partner_categories = selected_partner_category_ids and self.env['res.partner.category'].browse(selected_partner_category_ids) or self.env['res.partner.category']
        options['selected_partner_categories'] = selected_partner_categories.mapped('name')

    @api.model
    def _get_options_partner_domain(self, options):
        domains = []
        if options.get('partner_ids'):
            partner_ids = [int(partner) for partner in options['partner_ids']]
            domains.append(Domain('partner_id', 'in', partner_ids))
        if options.get('partner_categories'):
            partner_category_ids = [int(category) for category in options['partner_categories']]
            domains.append(Domain('partner_id.category_id', 'in', partner_category_ids))
        return Domain.AND(domains)

    ####################################################
    # OPTIONS: all_entries
    ####################################################

    @api.model
    def _get_options_all_entries_domain(self, options):
        if not options.get('all_entries'):
            return Domain('parent_state', '=', 'posted')
        else:
            return Domain('parent_state', '!=', 'cancel')

    ####################################################
    # OPTIONS: not reconciled entries
    ####################################################
    def _init_options_reconciled(self, options, previous_options):
        report_date_to = fields.Date.from_string(options['date']['date_to'])
        previous_date_to = fields.Date.from_string(previous_options.get('date', {}).get('date_to', ''))
        options['unreconciled'] = False
        options['recon_date'] = False
        if self.filter_unreconciled and report_date_to == previous_date_to:
            options['unreconciled'] = previous_options.get('unreconciled', False)
            if options['unreconciled']:
                previous_recon_date = self._get_option_recon_date(previous_options)
                recon_date = previous_recon_date or report_date_to or fields.Date.context_today(self)
                options['recon_date'] = {
                    'date_to': fields.Date.to_string(recon_date),
                    'date_to_str': format_date(self.env, recon_date) if recon_date else '',
                }

    @api.model
    def _get_option_recon_date(self, options):
        option_recon_date = options.get('recon_date') and options['recon_date'].get('date_to')
        return fields.Date.to_date(option_recon_date) if option_recon_date else False

    @api.model
    def _get_options_unreconciled_domain(self, options):
        if recon_date := self._get_option_recon_date(options):
            return (
                Domain('residual_at_date', '!=', 0.0) |
                Domain('full_reconcile_id', '=', False) |
                Domain('full_reconcile_id.reconciled_line_ids.date', '>', recon_date)
            ) & Domain('open_on', '=', recon_date)
        return Domain.TRUE

    ####################################################
    # OPTIONS: account_type
    ####################################################

    def _init_options_account_type(self, options, previous_options):
        '''
        Initialize a filter based on the account_type of the line (trade/non trade, payable/receivable).
        Selects a name to display according to the selections.
        The group display name is selected according to the display name of the options selected.
        '''
        if self.filter_account_type in ('disabled', False):
            return

        account_type_list = [
            {'id': 'trade_receivable', 'name': _("Receivable"), 'selected': True},
            {'id': 'non_trade_receivable', 'name': _("Non Trade Receivable"), 'selected': False},
            {'id': 'trade_payable', 'name': _("Payable"), 'selected': True},
            {'id': 'non_trade_payable', 'name': _("Non Trade Payable"), 'selected': False},
        ]

        if self.filter_account_type == 'receivable':
            options['account_type'] = account_type_list[:2]
        elif self.filter_account_type == 'payable':
            options['account_type'] = account_type_list[2:]
        else:
            options['account_type'] = account_type_list

        if previous_options.get('account_type'):
            previously_selected_ids = {x['id'] for x in previous_options['account_type'] if x.get('selected')}
            for opt in options['account_type']:
                opt['selected'] = opt['id'] in previously_selected_ids

    @api.model
    def _get_options_account_type_domain(self, options):
        all_domains = []
        selected_domains = []
        if not options.get('account_type') or len(options.get('account_type')) == 0:
            return Domain.TRUE
        for opt in options.get('account_type', []):
            if opt['id'] == 'trade_receivable':
                domain = [('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'asset_receivable')]
            elif opt['id'] == 'trade_payable':
                domain = [('account_id.non_trade', '=', False), ('account_id.account_type', '=', 'liability_payable')]
            elif opt['id'] == 'non_trade_receivable':
                domain = [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'asset_receivable')]
            elif opt['id'] == 'non_trade_payable':
                domain = [('account_id.non_trade', '=', True), ('account_id.account_type', '=', 'liability_payable')]
            if opt['selected']:
                selected_domains.append(domain)
            all_domains.append(domain)
        return Domain.OR(selected_domains or all_domains)

    ####################################################
    # OPTIONS: order column
    ####################################################

    @api.model
    def _init_options_order_column(self, options, previous_options):
        # options['order_column'] is in the form {'expression_label': expression label of the column to order, 'direction': the direction order ('ASC' or 'DESC')}
        options['order_column'] = None

        previous_value = previous_options and previous_options.get('order_column')
        if previous_value:
            for col in options['columns']:
                if col['sortable'] and col['expression_label'] == previous_value['expression_label']:
                    options['order_column'] = previous_value
                    break

    ####################################################
    # OPTIONS: hierarchy
    ####################################################

    def _init_options_hierarchy(self, options, previous_options):
        company_ids = self.get_report_company_ids(options)
        if self.filter_hierarchy != 'never' and self.env['account.account'].search_count(
            Domain.AND([
                self.env['account.account']._check_company_domain(company_ids),
                Domain('parent_id', '!=', False),
            ]),
            limit=1
        ):
            options['display_hierarchy_filter'] = True
            if 'hierarchy' in previous_options:
                options['hierarchy'] = previous_options['hierarchy']
            else:
                options['hierarchy'] = self.filter_hierarchy == 'by_default'
        else:
            options['hierarchy'] = False
            options['display_hierarchy_filter'] = False

    @api.model
    def _create_hierarchy(self, lines, options):
        """Compute the hierarchy and subtotals (when the option is activated) based on account parents.

        The hierarchy option is available only when there are account parents for the company and can be enabled/disabled.
        It should be called when before returning the lines to the client/templater.
        The lines are the result of _get_lines(). If there is a hierarchy, it is left untouched, only the lines related
        to an account parent-child relationship are put in a hierarchy according to the account's parent.
        """
        if not lines:
            return lines

        def create_hierarchy_line(account, column_totals, level, parent_id, unfoldable=True):
            line_id = self._get_generic_line_id('account.account', account.id, parent_line_id=parent_id, markup='parent_account')
            unfolded = line_id in options.get('unfolded_lines') or options['unfold_all']
            columns = []
            for column_total, column in zip(column_totals, options['columns']):
                if isinstance(column_total, tuple):
                    column_value, currency = column_total
                else:
                    column_value = column_total
                    currency = None

                columns.append(self._build_column_data(column_value, column, options=options, currency=currency))

            return AccountReportLineData(
                id=line_id,
                name=account.display_name,
                unfoldable=unfoldable,
                unfolded=unfolded,
                level=level,
                parent_id=parent_id,
                columns=columns
            )

        def compute_parent_totals(line, parent=None):
            totals = []

            for total, column in zip(hierarchy[parent]['totals'], line.columns):
                if not isinstance(column.no_format, (int, float)):
                    total = None

                if isinstance(total, (int, float)):
                    total = total + column.no_format
                elif isinstance(total, tuple):
                    if total == (None, None):
                        # Entering here only on first aggregation
                        amount = 0.0
                        currency = column.currency
                    else:
                        amount, currency = total

                    if currency != column.currency:
                        total = None
                    else:
                        total = (
                            amount + column.no_format,
                            currency
                        )

                totals.append(total)

            return totals

        def render_lines(account_parents, current_level, parent_line_id):
            to_treat = [(current_level, parent_line_id, parent) for parent in account_parents]

            while to_treat:
                level_to_apply, parent_id, parent = to_treat.pop(0)
                parent_data = hierarchy[parent]
                render_line_id = parent_id

                treated_child_accounts = self.env['account.account']

                if bool(parent_data['child_accounts']):
                    parent_total_line = create_hierarchy_line(parent, parent_data['totals'], level_to_apply, parent_id)
                    new_lines.append(parent_total_line)
                    render_line_id = parent_total_line.id
                    level_to_apply += 1

                for account_line in parent_data['lines']:
                    markup, model, account_id = self._parse_line_id(account_line.id)[-1]
                    account_line_id = self._get_generic_line_id(model, account_id, markup=markup, parent_line_id=render_line_id)
                    account_line.id = account_line_id
                    account_line.parent_id = render_line_id
                    account_line.level = level_to_apply
                    new_lines.append(account_line)

                    for child_account in parent_data['child_accounts']:
                        if child_account not in treated_child_accounts:
                            render_lines(child_account, level_to_apply, render_line_id)
                            treated_child_accounts += child_account

                    for child_line in account_line_children_map[account_id]:
                        markup, model, res_id = self._parse_line_id(child_line.id)[-1]
                        child_line.update_values(
                            id=self._get_generic_line_id(model, res_id, markup=markup, parent_line_id=account_line_id),
                            parent_id=account_line_id,
                            level=account_line.level + 1
                        )
                        new_lines.append(child_line)

                to_treat = [
                    (level_to_apply, render_line_id, child_group)
                    for child_group
                    in parent_data['child_accounts']
                    if child_group not in treated_child_accounts
                ] + to_treat

        def create_hierarchy_dict():
            def create_totals():
                totals = []

                for column in options['columns']:
                    default_value = None
                    if figure_type := column.get('figure_type'):
                        if figure_type == 'float':
                            default_value = 0.0
                        elif figure_type == 'integer':
                            default_value = 0
                        elif figure_type == 'monetary':
                            default_value = (None, None)
                    totals.append(default_value)

                return totals

            return defaultdict(lambda: {
                'lines': [],
                'totals': create_totals(),
                'child_accounts': self.env['account.account'],
            })

        # Precompute the account parents of the accounts in the report
        account_ids = []
        for line in lines:
            markup, res_model, model_id = self._parse_line_id(line.id)[-1]
            if res_model == 'account.account' and model_id:
                account_ids.append(model_id)

        new_lines, total_lines = [], []

        # root_line_id is the id of the parent line of the lines we want to render
        root_line_id = self._build_parent_line_id(self._parse_line_id(lines[0].id)) or None
        last_account_line_id = account_id = None
        current_level = 0
        account_line_children_map = defaultdict(list)
        account_parents = self.env['account.account']
        root_accounts = self.env['account.account']
        hierarchy = create_hierarchy_dict()

        for line in lines:
            markup, res_model, model_id = self._parse_line_id(line.id)[-1]

            # Account lines are used as the basis for the computation of the hierarchy.
            if res_model == 'account.account':
                last_account_line_id = line.id
                current_level = line.level
                account_id = model_id
                account = self.env[res_model].browse(account_id)
                account_parents = account.parent_ids[::-1]

                for i, parent in enumerate(account_parents):
                    if i == 0:
                        hierarchy[parent]['lines'].append(line)
                    if i == len(account_parents) - 1 and parent not in root_accounts:
                        root_accounts += parent
                    if parent.parent_id and parent not in hierarchy[parent.parent_id]['child_accounts']:
                        hierarchy[parent.parent_id]['child_accounts'] += parent

                    hierarchy[parent]['totals'] = compute_parent_totals(line, parent=parent)

            # This is not an account line, so we check to see if it is a descendant of the last account line.
            # If so, it is added to the mapping of the lines that are related to this account.
            elif last_account_line_id and (line.parent_id or '').startswith(last_account_line_id):
                account_line_children_map[account_id].append(line)

            # This is a total line that is not linked to an account. It is saved in order to be added at the end.
            elif markup == 'total':
                total_lines.append(line)

            # This line ends the scope of the current hierarchy and is (possibly) the root of a new hierarchy.
            # We render the current hierarchy and set up to build a new hierarchy
            else:
                render_lines(root_accounts, current_level, root_line_id)

                new_lines.append(line)

                # Reset the hierarchy-related variables for a new hierarchy
                root_line_id = line.id
                last_account_line_id = account_id = None
                current_level = 0
                account_line_children_map = defaultdict(list)
                root_accounts = self.env['account.account']
                account_parents = self.env['account.account']
                hierarchy = create_hierarchy_dict()

        render_lines(root_accounts, current_level, root_line_id)

        return new_lines + total_lines

    ####################################################
    # OPTIONS: MULTI COMPANY
    ####################################################

    def _init_options_companies(self, options, previous_options):
        if previous_options.get('forced_companies'):
            options['forced_companies'] = previous_options['forced_companies']
            companies = self.env.company.browse(previous_options['forced_companies'])
        elif self.filter_multi_company == 'tax_units':
            companies = self._multi_company_tax_units_init_options(options, previous_options=previous_options)
        else:
            # self.filter_multi_company == 'selector'
            companies = self.env.companies

        options['companies'] = [{'name': c.name, 'id': c.id, 'currency_id': c.currency_id.id} for c in companies]

    def _multi_company_tax_units_init_options(self, options, previous_options):
        """ Initializes the companies option for reports configured to compute it from tax units.
        """
        available_tax_units = self.env.company._get_available_tax_units(self)

        # Filter available units to only consider the ones whose companies are all accessible to the user
        available_tax_units = available_tax_units.filtered(
            lambda x: all(unit_company in self.env.user.company_ids for unit_company in x.sudo().company_ids)
            # sudo() to avoid bypassing companies the current user does not have access to
        )

        options['available_tax_units'] = [{
            'id': tax_unit.id,
            'name': tax_unit.name,
            'company_ids': tax_unit.company_ids.ids
        } for tax_unit in available_tax_units]

        # Available tax_unit option values that are currently allowed by the company selector
        # A js hack ensures the page is reloaded and the selected companies modified
        # when clicking on a tax unit option in the UI, so we don't need to worry about that here.
        companies_authorized_tax_unit_opt = {
            *(available_tax_units.filtered(lambda x: set(self.env.companies) == set(x.company_ids)).ids),
            'company_only'
        }

        if previous_options.get('tax_unit') in companies_authorized_tax_unit_opt:
            options['tax_unit'] = previous_options['tax_unit']

        else:
            # No tax_unit gotten from previous options; initialize it
            # A tax_unit will be set by default if only one tax unit is available for the report
            # (which should always be true for non-generic reports, which have a country), and the companies of
            # the unit are the only ones currently selected.
            if companies_authorized_tax_unit_opt == {'company_only'}:
                options['tax_unit'] = 'company_only'
            elif len(available_tax_units) == 1 and available_tax_units[0].id in companies_authorized_tax_unit_opt:
                options['tax_unit'] = available_tax_units[0].id
            else:
                options['tax_unit'] = 'company_only'

        # Finally initialize multi_company filter
        if options['tax_unit'] == 'company_only':
            companies = self.env.company._get_branches_with_same_vat(accessible_only=True)
        else:
            tax_unit = available_tax_units.filtered(lambda x: x.id == options['tax_unit'])
            companies = tax_unit.company_ids

        return companies

    ####################################################
    # OPTIONS: MULTI CURRENCY
    ####################################################
    def _init_options_multi_currency(self, options, previous_options):
        options['multi_currency'] = (
            any([company.get('currency_id') != options['companies'][0].get('currency_id') for company in options['companies']])
            or any([column.figure_type != 'monetary' for column in self.column_ids])
            or any(expression.figure_type and expression.figure_type != 'monetary' for expression in self.line_ids.expression_ids)
        )

    ####################################################
    # OPTIONS: ROUNDING UNIT
    ####################################################
    def _init_options_rounding_unit(self, options, previous_options):
        default = 'decimals'
        options['rounding_unit'] = previous_options.get('rounding_unit', default)
        options['rounding_unit_names'] = self._get_rounding_unit_names()

    def _get_rounding_unit_names(self):
        currency_symbol = self.env.company.currency_id.symbol
        currency_name = self.env.company.currency_id.name

        rounding_unit_names = [
            ('decimals', f'.{currency_symbol}'),
            ('units', f'{currency_symbol}'),
            ('thousands', f'k{currency_symbol}'),
            ('millions', f'M{currency_symbol}'),
        ]

        if currency_name in CURRENCIES_USING_LAKH:
            rounding_unit_names.insert(3, ('lakhs', f'L{currency_symbol}'))

        return dict(rounding_unit_names)

    # ####################################################
    # OPTIONS: ALL ENTRIES
    ####################################################
    def _init_options_all_entries(self, options, previous_options):
        if self.filter_show_draft:
            options['all_entries'] = previous_options.get('all_entries', False)
        else:
            options['all_entries'] = False

    ####################################################
    # OPTIONS: UNFOLDED LINES
    ####################################################
    def _init_options_unfolded(self, options, previous_options):
        options['unfold_all'] = self.filter_unfold_all and previous_options.get('unfold_all', False)

        previous_section_source_id = previous_options.get('sections_source_id')
        if not previous_section_source_id or previous_section_source_id == options['sections_source_id']:
            # Only keep the unfolded lines if they belong to the same report or a section of the same report
            options['unfolded_lines'] = previous_options.get('unfolded_lines', [])
        else:
            options['unfolded_lines'] = []

    ####################################################
    # OPTIONS: HIDE LINE AT 0
    ####################################################
    def _init_options_hide_0_lines(self, options, previous_options):
        if self.filter_hide_0_lines != 'never':
            previous_val = previous_options.get('hide_0_lines')
            if previous_val is not None:
                options['hide_0_lines'] = previous_val
            else:
                options['hide_0_lines'] = self.filter_hide_0_lines == 'by_default'
        else:
            options['hide_0_lines'] = False

    def _filter_out_0_lines(self, lines):
        """ Returns a list containing all lines that are not zero or that are parent to non-zero lines.
            Can be used to ensure printed report does not include 0 lines, when hide_0_lines is toggled.
        """
        lines_to_hide = set()  # contain line ids to remove from lines
        has_visible_children = set()  # contain parent line ids
        # Traverse lines in reverse to keep track of visible parent lines required by children lines
        for line in reversed(lines):
            is_zero_line = all(col.figure_type not in NUMBER_FIGURE_TYPES or col.is_zero for col in line.columns)
            if is_zero_line and line.id not in has_visible_children:
                lines_to_hide.add(line.id)
            if line.parent_id and line.id not in lines_to_hide:
                has_visible_children.add(line.parent_id)
        return list(filter(lambda x: x.id not in lines_to_hide, lines))

    ####################################################
    # OPTIONS: HORIZONTAL GROUP
    ####################################################
    def _init_options_horizontal_groups(self, options, previous_options):
        journal_groups = self._get_journal_groups()
        options['available_horizontal_groups'] = available_horizontal_groups = []
        available_horizontal_group_ids = set()
        group_ledger = self.env.ref('account_reports.horizontal_group_ledger')
        for horizontal_group in self.horizontal_group_ids:
            if (
                horizontal_group.id != group_ledger.id
                or journal_groups
                or len(options['companies']) > 1
            ):
                available_horizontal_group_ids.add(horizontal_group.id)
                available_horizontal_groups.append(
                    {
                        'id': horizontal_group.id,
                        'name': horizontal_group.name,
                    }
                )
        previous_selected = previous_options.get('selected_horizontal_group_id')
        options['selected_horizontal_group_id'] = previous_selected if previous_selected in available_horizontal_group_ids else None

    ####################################################
    # OPTIONS: SEARCH BAR
    ####################################################
    def _init_options_search_bar(self, options, previous_options):
        if self.search_bar:
            options['search_bar'] = True
            if 'filter_search_bar' in previous_options:
                options['filter_search_bar'] = previous_options['filter_search_bar']

    ####################################################
    # OPTIONS: COLUMN HEADERS
    ####################################################

    def _init_options_column_headers(self, options, previous_options):
        # Prepare column headers, in case the order of the comparison is ascending we reverse the order of the columns
        all_comparison_date_vals = ([options['date']] + options.get('comparison', {}).get('periods', []))
        if options.get('comparison') and options['comparison']['period_order'] == 'ascending':
            all_comparison_date_vals = all_comparison_date_vals[::-1]

        column_headers = [
            [
                {
                    'name': comparison_date_vals['string'],
                    'forced_options': {'date': comparison_date_vals},
                }
                for comparison_date_vals in all_comparison_date_vals
            ], # First level always consists of date comparison. Horizontal groupby are done on following levels.
        ]

        # Handle horizontal groups
        selected_horizontal_group_id = options.get('selected_horizontal_group_id')
        if selected_horizontal_group_id:
            horizontal_group = self.env['account.report.horizontal.group'].browse(selected_horizontal_group_id)

            for field_name, records in horizontal_group._get_header_levels_data():
                header_level = []
                # If horizontal group based on ledgers, adding the columns for the local journals each company
                if field_name == 'journal_group_id':
                    journal_groups_ids = {group['id'] for group in options.get('journal_groups', []) if group.get('selected')}
                    if not journal_groups_ids or 'local_gaap' in journal_groups_ids:
                        for company in self.env.companies:
                            header_level.append({
                                'name': company.display_name,
                                'horizontal_groupby_element': {
                                    'company_id': company.id,
                                    'journal_id': self._get_selected_journals_without_group(options, company).ids,
                                }
                            })
                    if journal_groups_ids:
                        records = records.filtered(lambda r: r.id in journal_groups_ids)
                header_level += [
                    {
                        'name': record.display_name,
                        'horizontal_groupby_element': {field_name: record.id},
                    }
                    for record in records
                ]
                column_headers.append(header_level)

        # Insert budget column headers if needed
        selected_budgets = [budget for budget in options.get('budgets', []) if budget['selected']]
        if selected_budgets:
            budget_headers = [{
                'name': _("Period Total"),
                'forced_options': {
                    'budget_base': True,
                    'no_subheader_division': True,
                },
                'colspan': len(self.column_ids),
            }]

            for budget in selected_budgets:
                # Add budget amount column
                budget_headers.append({
                    'name': budget['name'],
                    'forced_options': {
                        'compute_budget': budget['id'],
                        'no_subheader_division': True,
                    },
                    'colspan': 1,
                })
                # Add budget percentage column
                budget_headers.append({
                    'name': "%",
                    'forced_options': {
                        'budget_percentage': budget['id'],
                        'no_subheader_division': True,
                    },
                    'colspan': 1,
                })

            if selected_horizontal_group_id:
                column_headers[1] += budget_headers
            else:
                column_headers.append(budget_headers)

        options['column_headers'] = column_headers

    ####################################################
    # OPTIONS: COLUMNS
    ####################################################
    def _init_options_columns(self, options, previous_options):
        default_group_vals = {'horizontal_groupby_element': {}, 'forced_options': {}}
        all_column_group_vals_in_order = self._generate_columns_group_vals_recursively(options['column_headers'], default_group_vals)

        options['columns'] = self._build_columns_from_column_group_vals(options, all_column_group_vals_in_order)

        # Debug column is only shown when there is a single column group, so that we can display all the subtotals of the line in a clear way
        options['show_debug_column'] = options['export_mode'] != 'print' \
                                       and self.env.user.has_group('base.group_no_one') \
                                       and len(options['column_groups']) == 1 \
                                       and len(self.line_ids) > 0 # No debug column on fully dynamic reports by default (they can customize this)

        options['show_last_annotations'] = previous_options.get('show_last_annotations')

        selected_budgets = [budget for budget in options.get('budgets', []) if budget['selected']]

        # In case the line comparison feature is used together with a feature using column groups, we disable it here and reset the comparison filter.
        if options.get('comparison', {}).get('filter') == 'report_line' and len(options['column_groups']) > 1:
            options['comparison']['filter'] = 'no_comparison'
            del options['comparison']['base_report_line']

        # Show an additional column summing all the horizontal groups if there is no comparison or budget, and only one level of horizontal group
        options['show_horizontal_group_total'] = options.get('selected_horizontal_group_id') \
                                                 and options.get('comparison', {}).get('filter') == 'no_comparison' \
                                                 and len(self.column_ids) == 1 \
                                                 and len(options['column_headers']) == 2 \
                                                 and not selected_budgets

    def _generate_columns_group_vals_recursively(self, next_levels_headers, previous_levels_group_vals):
        if next_levels_headers:
            rslt = []

            # Separate headers into those with "no_subheader_division" and those without
            headers_with_no_subdivision = [
                header for header in next_levels_headers[0]
                if 'no_subheader_division' in header.get('forced_options', {})
            ]
            valid_next_level_headers = [
                header for header in next_levels_headers[0]
                if 'no_subheader_division' not in header.get('forced_options', {})
            ]

            # Process headers without "no_subheader_division"
            for header_element in valid_next_level_headers:
                current_level_group_vals = {
                    key: {**previous_levels_group_vals.get(key, {}), **header_element.get(key, {})}
                    for key in previous_levels_group_vals
                }
                rslt += self._generate_columns_group_vals_recursively(next_levels_headers[1:], current_level_group_vals)

            # Process headers with "no_subheader_division" as standalone groups
            for header_element in headers_with_no_subdivision:
                current_level_group_vals = {
                    key: {**previous_levels_group_vals.get(key, {}), **header_element.get(key, {})}
                    for key in previous_levels_group_vals
                }
                rslt.append(current_level_group_vals)

            return rslt
        else:
            return [previous_levels_group_vals]

    def _build_columns_from_column_group_vals(self, options, all_column_group_vals_in_order):
        def _generate_domain_from_horizontal_group_hash_key_tuple(group_hash_key):
            domain = []
            for field_name, field_value in group_hash_key:
                operator = 'in' if isinstance(field_value, (list, tuple)) else '='
                domain.append((field_name, operator, field_value))
            return domain

        columns = []
        options.setdefault('column_groups', [])
        for column_group_val in all_column_group_vals_in_order:
            horizontal_group_key_tuple = self._get_dict_hashable_key_tuple(column_group_val['horizontal_groupby_element']) # Empty tuple if no grouping
            column_group_index = str(self._get_dict_hashable_key_tuple(column_group_val))  # Unique identifier for the column group

            column_group = {
                'forced_options': column_group_val['forced_options'],
                'forced_domain': _generate_domain_from_horizontal_group_hash_key_tuple(horizontal_group_key_tuple),
            }
            if horizontal_group_key_tuple:
                column_group['horizontal_groupby_element'] = horizontal_group_key_tuple

            options['column_groups'].append(column_group)
            column_group_index = len(options['column_groups']) - 1
            # for budget, only one column in needed, regardless of the number of columns in the report
            if any(budget_key in column_group_val['forced_options'] for budget_key in ('compute_budget', 'budget_percentage')):
                columns.append({
                    'name': "",
                    'column_group_index': column_group_index,
                    'expression_label': 'balance',
                    'sortable': False,
                    'figure_type': 'monetary',
                    'blank_if_zero': False,
                })

            else:
                for report_column in self.column_ids:
                    columns.append({
                        'name': report_column.name,
                        'column_group_index': column_group_index,
                        'expression_label': report_column.expression_label,
                        'sortable': report_column.sortable,
                        'figure_type': report_column.figure_type,
                        'blank_if_zero': report_column.blank_if_zero,
                        'class': f"text-nowrap {'text-end numeric-header' if report_column.figure_type in NUMBER_FIGURE_TYPES else 'text-center'}",
                    })

        return columns

    def _get_dict_hashable_key_tuple(self, dict_to_convert):
        rslt = []
        for key, value in sorted(dict_to_convert.items()):
            if isinstance(value, dict):
                value = self._get_dict_hashable_key_tuple(value)
            rslt.append((key, value))
        return tuple(rslt)

    ####################################################
    # OPTIONS: BUTTONS
    ####################################################

    def action_open_report_form(self, options, params):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.report',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_id': self.id,
        }

    def _init_options_buttons(self, options, previous_options):
        options['buttons'] = [
            {'name': _('Print'), 'sequence': 10, 'action': 'export_file', 'action_param': 'export_to_pdf', 'file_export_type': _('PDF'), 'branch_allowed': True, 'always_show': True},
            {'name': _('XLSX'), 'sequence': 20, 'action': 'export_file', 'action_param': 'export_to_xlsx', 'file_export_type': _('XLSX'), 'branch_allowed': True, 'always_show': False},
        ]

    def open_account_report_file_download_error_wizard(self, errors, content):
        self.ensure_one()

        model = 'account.report.file.download.error.wizard'
        vals = {'actionable_errors': errors}

        if content:
            vals['file_name'] = content['file_name']
            vals['file_content'] = BinaryBytes(re.sub(r'\n\s*\n', '\n', content['file_content']).encode())

        return {
            'type': 'ir.actions.act_window',
            'res_model': model,
            'res_id': self.env[model].create(vals).id,
            'target': 'new',
            'views': [(False, 'form')],
        }

    def get_export_mime_type(self, file_type):
        """ Returns the MIME type associated with a report export file type,
        for attachment generation.
        """
        type_mapping = {
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'pdf': 'application/pdf',
            'xml': 'application/xml',
            'xaf': 'application/vnd.sun.xml.writer',
            'txt': 'text/plain',
            'csv': 'text/csv',
            'zip': 'application/zip',
        }
        return type_mapping.get(file_type, False)

    def _init_options_section_buttons(self, options, previous_options):
        """ In case we're displaying a section, we want to replace its buttons by its source report's. This needs to be done last, after calling the
        custom handler, to avoid its _custom_options_initializer function to generate additional buttons.
        """
        if options['sections_source_id'] != self.id:
            # We need to re-call a full get_options in case a custom options initializer adds new buttons depending on other options.
            # This way, we're sure we always get all buttons that are needed.
            sections_source = self.env['account.report'].browse(options['sections_source_id'])
            options['buttons'] = sections_source.get_options(previous_options={**options, 'no_report_reroute': True})['buttons']

    ####################################################
    # OPTIONS: VARIANTS
    ####################################################
    def _init_options_variants(self, options, previous_options):
        allowed_variant_ids = set()

        previous_section_source_id = previous_options.get('sections_source_id')
        if previous_section_source_id:
            previous_section_source = self.env['account.report'].browse(previous_section_source_id)
            if self in previous_section_source.section_report_ids:
                options['variants_source_id'] = (previous_section_source.root_report_id or previous_section_source).id
                allowed_variant_ids.add(previous_section_source_id)

        if 'variants_source_id' not in options:
            options['variants_source_id'] = (self.root_report_id or self).id

        available_variants = self.env['account.report']
        options['has_inactive_variants'] = False
        allowed_country_variant_ids = {}
        allowed_consolidation_variant_ids = []
        all_variants = self._get_variants(options['variants_source_id'])
        for variant in all_variants._is_available_for(self.env['res.company'].browse(self.get_report_company_ids(options))):
            if not self.root_report_id and variant != self and variant.active: # Non-route reports don't reroute the variant when computing their options
                allowed_variant_ids.add(variant.id)
                if variant.country_id:
                    allowed_country_variant_ids.setdefault(variant.country_id.id, []).append(variant.id)
                if variant.availability_condition == 'consolidation':
                    allowed_consolidation_variant_ids.append(variant.id)

            if variant.active:
                available_variants += variant
            else:
                options['has_inactive_variants'] = True

        options['available_variants'] = [
            {
                'id': variant.id,
                'name': variant.display_name,
                'country_id': variant.country_id.id,  # To ease selection of default variant to open, without needing browsing again
            }
            for variant in sorted(available_variants, key=lambda x: (x.country_id and 1 or 0, x.sequence, x.id))
        ]

        previous_opt_report_id = previous_options.get('selected_variant_id')
        if previous_opt_report_id in allowed_variant_ids or previous_opt_report_id == self.id:
            options['selected_variant_id'] = previous_opt_report_id
        elif allowed_consolidation_variant_ids:
            options['selected_variant_id'] = allowed_consolidation_variant_ids[0]
        elif allowed_country_variant_ids:
            country_id = self.env.company.account_fiscal_country_id.id
            report_id = (allowed_country_variant_ids.get(country_id) or next(iter(allowed_country_variant_ids.values())))[0]
            options['selected_variant_id'] = report_id
        else:
            options['selected_variant_id'] = self.id

    def _get_variants(self, report_id):
        source_report = self.env['account.report'].browse(report_id)
        if source_report.root_report_id:
            # We need to get the root report in order to get all variants
            source_report = source_report.root_report_id
        return source_report + source_report.with_context(active_test=False).variant_report_ids

    ####################################################
    # OPTIONS: SECTIONS
    ####################################################
    def _init_options_sections(self, options, previous_options):
        if options.get('selected_variant_id'):
            options['sections_source_id'] = options['selected_variant_id']
        else:
            options['sections_source_id'] = self.id

        source_report = self.env['account.report'].browse(options['sections_source_id'])

        available_sections = source_report.section_report_ids if source_report.use_sections else self.env['account.report']
        options['sections'] = [{'name': section.name, 'id': section.id} for section in available_sections]

        if available_sections:
            section_id = previous_options.get('selected_section_id')
            if not section_id or section_id not in available_sections.ids:
                section_id = available_sections[0].id

            options['selected_section_id'] = section_id

        options['has_inactive_sections'] = bool(self.env['account.report'].with_context(active_test=False).search_count([
                ('section_main_report_ids', 'in', options['sections_source_id']),
                ('active', '=', False)
        ]))

    ####################################################
    # OPTIONS: REPORT_ID
    ####################################################
    def _init_options_report_id(self, options, previous_options):
        if previous_options.get('no_report_reroute'):
            # Used for exports
            options['report_id'] = self.id
        else:
            options['report_id'] = options.get('selected_section_id') or options.get('selected_variant_id') or self.id

    ####################################################
    # OPTIONS: EXPORT
    ####################################################
    def _init_options_export_mode(self, options, previous_options):
        options['export_mode'] = previous_options.get('export_mode')

    def _init_options_export(self, options, previous_options):
        options['report_title'] = previous_options.get('report_title')

    ####################################################
    # OPTIONS: HORIZONTAL SPLIT
    ####################################################
    def _init_options_horizontal_split(self, options, previous_options):
        if any(line.horizontal_split_side for line in self.line_ids):
            options['horizontal_split'] = previous_options.get('horizontal_split', False)

    ####################################################
    # OPTIONS: CUSTOM
    ####################################################
    def _init_options_custom(self, options, previous_options):
        custom_handler_model = self._get_custom_handler_model()
        if custom_handler_model:
            self.env[custom_handler_model]._custom_options_initializer(self, options, previous_options)

    ####################################################
    # OPTIONS: INTEGER ROUNDING
    ####################################################
    def _init_options_integer_rounding(self, options, previous_options):
        if self.integer_rounding:
            options['integer_rounding'] = self.integer_rounding
            if options.get('export_mode') == 'file':
                options['integer_rounding_enabled'] = True
            else:
                options['integer_rounding_enabled'] = previous_options.get('integer_rounding_enabled', True)
            return options

    ####################################################
    # OPTIONS: CONSOLIDATION
    ####################################################
    def _init_options_consolidation(self, options, previous_options):
        options['show_consolidation'] = len(self.get_report_company_ids(options)) > 1 and any(
            groupby.strip() == 'account_id'
            for groupby_str in self.line_ids.mapped('user_groupby')
            for groupby in (groupby_str or self.user_groupby or '').split(',')
        )

        switch_to_consolidation = len(previous_options.get('companies', [])) == 1 and len(options['companies']) > 1
        options['consolidation'] = options['show_consolidation'] and (previous_options.get('consolidation', True) or switch_to_consolidation)

    ####################################################
    # OPTIONS: BUDGETS
    ####################################################
    def _init_options_budgets(self, options, previous_options):
        if self.filter_budgets:
            previous_selection = {budget_option['id'] for budget_option in previous_options.get('budgets', []) if budget_option.get('selected')}

            options['budgets'] = [
                {
                    'id': budget.id,
                    'name': budget.name,
                    'selected': budget.id in previous_selection,
                    'company_id': budget.company_id.id,
                }
                for budget in self.env['account.report.budget'].search([('company_id', '=', self.env.company.id)])
            ]
            options['show_all_accounts'] = previous_options.get('show_all_accounts') or False

    ####################################################
    # OPTIONS: READONLY QUERY
    ####################################################
    def _init_options_readonly_query(self, options, previous_options):
        options['readonly_query'] = True

    ####################################################
    # OPTIONS: FILTERS
    ####################################################
    def _init_options_filters(self, options, previous_options):
        options['filters'] = {
            'show_all': self.filter_unfold_all,
            'show_analytic': options.get('display_analytic', False),
            'show_analytic_groupby': options.get('display_analytic_groupby', False),
            'show_analytic_plan_groupby': options.get('display_analytic_plan_groupby', False),
            'show_draft': self.filter_show_draft,
            'show_hierarchy': options.get('display_hierarchy_filter', False),
            'show_period_comparison': self.filter_period_comparison,
            'show_line_comparison': self.filter_line_comparison and len(options.get('comparison', {}).get('periods', [])) == len(options['column_groups']) - 1,
            'show_totals': self.env.company.totals_below_sections and not options.get('ignore_totals_below_sections'),
            'show_unreconciled': self.filter_unreconciled,
            'show_hide_0_lines': self.filter_hide_0_lines,
            'show_journals': self.filter_journals,
        }

    ####################################################
    # OPTIONS: USER GROUPS
    ####################################################
    def _init_options_user_groups(self, options, previous_options):
        options['user_groups'] = {
            'analytic_accounting': self.env.user.has_group('analytic.group_analytic_accounting'),
            'account_readonly': self.env.user.has_group('account.group_account_readonly'),
            'account_user': self.env.user.has_group('account.group_account_user'),
        }

    ####################################################
    # OPTIONS: CORE
    ####################################################
    @api.readonly
    def get_options(self, previous_options):
        self.ensure_one()

        initializers_in_sequence = self._get_options_initializers_in_sequence()

        options = {'custom_display_config': {}}

        if previous_options.get('_running_export_test'):
            options['_running_export_test'] = True

        idx = None
        with contextlib.suppress(ValueError):
            idx = initializers_in_sequence.index(self._init_options_report_id) + 1

        before_report = initializers_in_sequence[:idx]
        after_report = initializers_in_sequence[idx:]

        # We need report_id to be initialized. Compute the necessary options to check for reroute.
        for initializer in before_report:
            initializer(options, previous_options=previous_options)

        # Stop the computation to check for reroute once we have computed the necessary information
        if (not self.root_report_id or (self.use_sections and self.section_report_ids)) and options['report_id'] != self.id:
            # Load the variant/section instead of the root report
            variant_options = {**previous_options}
            for reroute_opt_key in ('selected_variant_id', 'selected_section_id', 'variants_source_id', 'sections_source_id'):
                opt_val = options.get(reroute_opt_key)
                if opt_val:
                    variant_options[reroute_opt_key] = opt_val

            return self.env['account.report'].browse(options['report_id']).get_options(variant_options)

        # No reroute; keep on and compute the other options
        for initializer in after_report:
            initializer(options, previous_options=previous_options)

        options_companies = self.env['res.company'].browse(self.get_report_company_ids(options))
        # Set export buttons to 'branch_allowed' if the currently selected company branches all share the same VAT
        # number and no unselected sub-branch of the active company has the same VAT number. Companies with an empty VAT
        # field will be considered as having the same VAT number as their closest parent with a non-empty VAT.
        if options.get('enable_export_buttons_for_common_vat_in_branches'):
            report_accepted_company_ids = set(options_companies.ids)
            same_vat_branch_ids = set(self.env.company._get_branches_with_same_vat().ids)
            if report_accepted_company_ids == same_vat_branch_ids:
                options['buttons'] = [{**button, 'branch_allowed': button.get('branch_allowed', True)} for button in options['buttons']]

        # Disable buttons without branch_allowed = True if not all branches are selected
        if not options_companies._all_branches_selected():
            for button in filter(lambda x: not x.get('branch_allowed'), options['buttons']):
                button['error_action'] = 'show_error_branch_allowed'

        # Sort the buttons list by sequence, for rendering
        options['buttons'] = sorted(options['buttons'], key=lambda x: x.get('sequence', 90))

        # Sanitizing date_from and date_to since they need to be JSON-serializable when exporting the report
        # on the server side, since the ORM converts them to strings automatically when sending them to the client.
        for date_dict in (
            [options.get('date', {})] +
            [group_data['forced_options']['date'] for group_data in options['column_groups'] if group_data.get('forced_options', {}).get('date')]
        ):
            if (date_from := date_dict.get('date_from')) and not isinstance(date_from, str):
                date_dict['date_from'] = fields.Date.to_string(date_from)

            if (date_to := date_dict.get('date_to')) and not isinstance(date_to, str):
                date_dict['date_to'] = fields.Date.to_string(date_to)

        # Sanitizing custom_ranges too
        filter_date_years = options['filter_date']['filters'].get('year', {})
        if custom_ranges := filter_date_years.get('custom_ranges'):
            filter_date_years['custom_ranges'] = [
                (
                    fields.Date.to_string(date_from) if not isinstance(date_from, str) else date_from,
                    fields.Date.to_string(date_to) if not isinstance(date_to, str) else date_to,
                    name
                )
                for (date_from, date_to, name) in custom_ranges
            ]

        return options

    def _get_options_initializers_in_sequence(self):
        """ Gets all filters in the right order to initialize them, so that each filter is
        guaranteed to be after all of its dependencies in the resulting list.

        :return: a list of initializer functions, each accepting two parameters:
            - options (mandatory): The options dictionary to be modified by this initializer to include its related option's data

            - previous_options (optional, defaults to None): A dict with default options values, coming from a previous call to the report.
                                                             These values can be considered or ignored on a case-by-case basis by the initializer,
                                                             depending on functional needs.
        """
        initializer_prefix = '_init_options_'
        initializers = [
            getattr(self, attr) for attr in dir(self)
            if attr.startswith(initializer_prefix)
        ]

        # Order them in a dependency-compliant way
        forced_sequence_map = self._get_options_initializers_forced_sequence_map()
        initializers.sort(key=lambda x: forced_sequence_map.get(x, forced_sequence_map.get('default')))

        return initializers

    def _get_options_initializers_forced_sequence_map(self):
        """ By default, not specific order is ensured for the filters when calling _get_options_initializers_in_sequence.
        This function allows giving them a sequence number. It can be overridden
        to make filters depend on each other.

        :return: dict(str, int): str is the filter name, int is its sequence (lowest = first).
                                 Multiple filters may share the same sequence, their relative order is then not guaranteed.
        """
        return {
            self._init_options_companies: 10,
            self._init_options_variants: 15,
            self._init_options_sections: 16,
            self._init_options_report_id: 17,
            self._init_options_return_periodicity: 29,
            self._init_options_filter_date: 30,
            self._init_options_date: 31,
            self._init_options_horizontal_groups: 40,
            self._init_options_comparison: 50,
            self._init_options_export_mode: 60,
            self._init_options_integer_rounding: 70,
            self._init_options_consolidation: 75,
            self._init_options_journals: 80,
            self._init_options_journals_names: 90,
            self._init_options_audit: 100,

            'default': 200,

            self._init_options_column_headers: 990,
            self._init_options_columns: 1000,
            self._init_options_column_percent_comparison: 1010,
            self._init_options_order_column: 1020,
            self._init_options_hierarchy: 1030,
            self._init_options_custom: 1050,
            self._init_options_section_buttons: 1060,
            self._init_options_readonly_query: 1070,
            self._init_options_filters: 1500,
        }

    def _get_options_domain(self, options, date_scope) -> Domain:
        self.ensure_one()

        available_scopes = dict(self.env['account.report.expression']._fields['date_scope'].selection)
        if date_scope and date_scope not in available_scopes: # date_scope can be passed to None explicitly to ignore the dates
            raise UserError(_("Unknown date scope: %s", date_scope))

        domains = [
            Domain('display_type', 'not in', ('line_section', 'line_subsection', 'line_note')),
            Domain('company_id', 'in', self.get_report_company_ids(options)),
            self._get_options_journals_domain(options)
            if not options.get('compute_budget') else Domain.TRUE,
            self._get_options_date_domain(options, date_scope)
            if date_scope else Domain.TRUE,
            self._get_options_partner_domain(options),
            self._get_options_all_entries_domain(options),
            self._get_options_unreconciled_domain(options),
            self._get_options_account_type_domain(options),
            self._get_options_aml_ir_filters(options),
            self.env['account.move.line']._get_tax_exigible_domain()
            if self.only_tax_exigible else Domain.TRUE,
            # That option key is set when splitting options between column groups
            options.get('forced_domain') or Domain.TRUE,
        ]

        # Handle foreign VAT
        if self.allow_foreign_vat:
            if self.country_id == self.env.company.account_fiscal_country_id:
                # It's a domestic report
                domains.append([
                    '|', '|',
                    ('move_id.fiscal_position_id', '=', False),
                    ('move_id.fiscal_position_id.foreign_vat', '=', False),
                    ('tax_tag_ids.country_id', '=', self.country_id.id),  # To allow setting loca tags on an operation made nor another country (sometimes legally necessary)
                ])
            elif self.country_id:
                # It's a foreign report
                domains.append([
                    '|',
                    ('tax_tag_ids.country_id', '=', self.country_id.id),  # To allow setting loca tags on an operation made nor another country (sometimes legally necessary)
                    '&',
                    ('move_id.fiscal_position_id.country_id', '=', self.country_id.id),
                    ('move_id.fiscal_position_id.foreign_vat', '!=', False),
                ])
            # else: don't filter anything; the report has no county and should have access to all the data

        return Domain.AND(domains)

    ####################################################
    # QUERIES
    ####################################################

    def _get_report_query(self, options, date_scope, domain=None, cta_date_to=None) -> Query:
        """ Get a Query object that references the records needed for this report. """
        domain = self._get_options_domain(options, date_scope) & Domain(domain or Domain.TRUE)
        date_from, date_to = self._get_date_bounds_info(options, date_scope)

        if options.get('compute_budget'):
            # remove required columns that are not filled from the domain
            # these are not in the budget table
            domain = domain.optimize(self.env['account.move.line'])
            aml_required_columns = {'move_id', 'currency_id', 'journal_id', 'display_type'}
            domain = domain.map_conditions(lambda condition: Domain.TRUE if condition.field_expr in aml_required_columns else condition)

        # The bypass below will ignore access rules ; we still want to check access
        if not self.env.user.has_groups('account.group_account_readonly,account.group_account_basic') and not self.env.su:
            raise AccessError(_("You must be an accountant to access accounting reports."))

        query = self.env['account.move.line'].with_context(
            date_from=date_from,
            date_to=cta_date_to or date_to,
            currency_translation=self.currency_translation,
            allowed_company_ids=self.env['account.report'].get_report_company_ids(options),
        )._search(domain, bypass_access=True)

        if options.get('compute_budget'):
            join, sql, condition = query._joins['account_move_line']
            sql = self._create_aml_shadowing_query_for_budget(options)
            query._joins['account_move_line'] = join, sql, condition
            query.add_where(SQL(
                "%s AND budget_id = %s",
                query.where_clause,
                options['compute_budget'],
            ))

        return query

    def _create_aml_shadowing_query_for_budget(self, options):
        _stored_fields, fields_to_insert = self.env['account.move.line']._prepare_aml_shadowing_for_report({
            'id': SQL.identifier("id"),
            'balance': SQL.identifier('amount'),
            'company_id': self.env.company.id,
            'parent_state': 'posted',
            'date': SQL.identifier('date'),
            'account_id': SQL.identifier("account_id"),
            'debit': SQL("CASE WHEN (amount > 0) THEN amount else 0 END"),
            'credit': SQL("CASE WHEN (amount < 0) THEN -amount else 0 END"),
        })

        queries = [SQL(
            """
                SELECT %(fields_to_insert)s, budget_id
                FROM account_report_budget_item
                WHERE budget_id IN %(available_budget_ids)s
            """,
            fields_to_insert=fields_to_insert,
            available_budget_ids=tuple(budget_option['id'] for budget_option in options['budgets']),
        )]

        if options.get('show_all_accounts'):
            _stored_fields, fields_to_insert = self.env['account.move.line']._prepare_aml_shadowing_for_report({
                # Using nextval will consume a sequence number, we decide to do it to avoid comparing apples and oranges
                'id': SQL("(SELECT nextval('account_report_budget_item_id_seq'))"),
                'balance': SQL("0"),
                'company_id': self.env.company.id,
                'parent_state': 'posted',
                'date': SQL("%s", options['date']['date_from']),
                'account_id': SQL.identifier("accounts", "id"),
                'debit': SQL("0"),
                'credit': SQL("0"),
            })
            accounts_subquery = self.env['account.account'].sudo()._search([
                ('company_ids', 'in', self.get_report_company_ids(options)),
                ('internal_group', 'in', ['income', 'expense']),
            ])

            queries.append(SQL(
                """
                    SELECT %(fields_to_insert)s, budgets.id AS budget_id
                    FROM (%(accounts_subquery)s) AS accounts
                    CROSS JOIN (
                        SELECT id
                        FROM account_report_budget
                        WHERE id IN %(available_budget_ids)s
                    ) AS budgets
                """,
                fields_to_insert=fields_to_insert,
                accounts_subquery=accounts_subquery.select(),
                available_budget_ids=tuple(budget_option['id'] for budget_option in options['budgets']),
                income='income%',
                expense='expense%',
                company_ids=tuple(),
            ))

        return SQL('(%s)', SQL(' UNION ALL ').join(queries))

    ####################################################
    # LINE IDS MANAGEMENT HELPERS
    ####################################################
    def _get_generic_line_id(self, model_name, value, markup=None, parent_line_id=None):
        """ Generates a generic line id from the provided parameters.

        Such a generic id consists of a string repeating 1 to n times the following pattern:
        markup-model-value, each occurence separated by a LINE_ID_HIERARCHY_DELIMITER character from the previous one.

        Each pattern corresponds to a level of hierarchy in the report, so that
        the n-1 patterns starting the id of a line actually form the id of its generator line.
        EX: a~b~c|d~e~f|g~h~i => This line is a subline generated by a~b~c|d~e~f where | is the LINE_ID_HIERARCHY_DELIMITER.

        Each pattern consists of the three following elements:
        - markup:  a (possibly empty) free string or json-formatted dict allowing finer identification of the line
                   (like the name of the field for account.accounting.reports)

        - model:   the model this line has been generated for, or an empty string if there is none

        - value:   the groupby value for this line (typically the id of a record
                   or the value of a field), or an empty string if there isn't any.
        """
        self.ensure_one()

        if parent_line_id:
            parent_id_list = self._parse_line_id(parent_line_id, markup_as_string=True)
        else:
            parent_id_list = [(None, 'account.report', self.id)]

        # In case the markup is a dict, it must be converted to a string, but in a way such that the keys are ordered alphabetically.
        # This is useful, notably for annotations where the ids of the lines are stored, therefore requiring a consistent ordering
        if isinstance(markup, dict):
            markup = json.dumps(markup, sort_keys=True)

        new_line = self._build_line_id(parent_id_list + [(markup, model_name, value)])
        return new_line

    @api.model
    def _get_line_from_xml_id(self, lines, xml_id):
        """ Helper function to get a specific account report line from the xmlid.

            :returns: The matching line dictionary if found. Otherwise,
                      an empty AccountReportLineData (instead of a StopIteration error).
            :rtype: dict
        """
        report_line = self.env.ref(xml_id, raise_if_not_found=False)
        if not report_line:
            return {}

        return next(iter(
            line for line in lines
            if self._get_model_info_from_id(line.id) == ('account.report.line', report_line.id)
        ), AccountReportLineData())

    @api.model
    def _get_model_info_from_id(self, line_id, include_markup=False):
        """ Parse the provided generic report line id.

        :param line_id: the report line id (i.e. markup~model~value|markup2~model2~value2 where | is the LINE_ID_HIERARCHY_DELIMITER)
        :return: tuple(model, id) of the report line. Each of those values can be None if the id contains no information about them.
        """
        last_id_tuple = self._parse_line_id(line_id)[-1]
        return last_id_tuple if include_markup else last_id_tuple[-2:]

    @api.model
    def _build_line_id(self, current):
        """ Build a generic line id string from its list representation, converting
        the None values for model and value to empty strings.
        :param current (list<tuple>): list of tuple(markup, model, value)
        """
        def convert_none(x):
            return x if x is not None and x is not False else ''
        return LINE_ID_HIERARCHY_DELIMITER.join(f'{convert_none(markup)}~{convert_none(model)}~{convert_none(value)}' for markup, model, value in current)

    @api.model
    def _build_parent_line_id(self, current):
        """Build the parent_line id based on the current position in the report.

        For instance, if current is [('markup1', 'account.account', 5), ('markup2', 'res.partner', 8)], it will return
        markup1~account.account~5
        :param current (list<tuple>): list of tuple(markup, model, value)
        """
        to_process = [(json.dumps(markup) if isinstance(markup, dict) else markup, model, value) for markup, model, value in current[:-1]]
        return self._build_line_id(to_process)

    @api.model
    def _parse_markup(self, markup):
        if not markup:
            return markup
        try:
            result = json.loads(markup)
        except json.JSONDecodeError:  # the markup is not a JSON object
            return markup
        if isinstance(result, dict):
            return result

        return markup

    @api.model
    def _parse_line_id(self, line_id, markup_as_string=False):
        """Parse the provided string line id and convert it to its list representation.
        Empty strings for model and value will be converted to None.

        For instance if line_id is markup1~account.account~5|markup2~res.partner~8 (where | is the LINE_ID_HIERARCHY_DELIMITER),
        it will return [('markup1', 'account.account', 5), ('markup2', 'res.partner', 8)]
        :param line_id (str): the generic line id to parse
        """
        return line_id and [
            # When there is a model, value is an id, so we cast it to and int. Else, we keep the original value (for groupby lines on
            # non-relational fields, for example).
            (self._parse_markup(markup) if not markup_as_string else markup, model or None, int(value) if model and value else (value or None))
            for markup, model, value in (key.rsplit('~', 2) for key in line_id.split(LINE_ID_HIERARCHY_DELIMITER))
        ] or []

    @api.model
    def _get_unfolded_lines(self, lines, parent_line_id):
        """ Return a list of all children lines for specified parent_line_id.
        NB: It will return the parent_line itself!

        For instance if parent_line_ids is '~account.report.line~84|{"groupby": "currency_id"}~res.currency~174'
        (where | is the LINE_ID_HIERARCHY_DELIMITER), it will return every subline for this currency.
        :param lines: list of report lines
        :param parent_line_id: id of a specified line
        :return: A list of all children lines for a specified parent_line_id
        """
        return [
            line for line in lines
            if line.id.startswith(parent_line_id)
        ]

    @api.model
    def _get_res_id_from_line_id(self, line_id, target_model_name):
        """ Parses the provided generic line id and returns the most local (i.e. the furthest on the right) record id it contains which
        corresponds to the provided model name. If line_id does not contain anything related to target_model_name, None will be returned.

        For example, parsing ~account.move~1|~res.partner~2|~account.move~3 (where | is the LINE_ID_HIERARCHY_DELIMITER)
        with target_model_name='account.move' will return 3.
        """
        dict_result = self._get_res_ids_from_line_id(line_id, [target_model_name])
        return dict_result[target_model_name] if dict_result else None


    @api.model
    def _get_res_ids_from_line_id(self, line_id, target_model_names):
        """ Parses the provided generic line id and returns the most local (i.e. the furthest on the right) record ids it contains which
        correspond to the provided model names, in the form {model_name: res_id}. If a model is not present in line_id, its model will be absent
        from the resulting dict.

        For example, parsing ~account.move~1|~res.partner~2|~account.move~3 with target_model_names=['account.move', 'res.partner'] will return
        {'account.move': 3, 'res.partner': 2}.
        """
        result = {}
        models_to_find = set(target_model_names)
        for _markup, model, value in reversed(self._parse_line_id(line_id)):
            if model in models_to_find:
                result[model] = value
                models_to_find.remove(model)

        return result

    @api.model
    def _get_markup(self, line_id):
        """ Directly returns the markup associated with the provided line_id.
        """
        return self._parse_line_id(line_id)[-1][0] if line_id else None

    def _build_subline_id(self, parent_line_id, subline_id_postfix):
        """ Creates a new subline id by concatanating parent_line_id with the provided id postfix.
        """
        return f"{parent_line_id}{LINE_ID_HIERARCHY_DELIMITER}{subline_id_postfix}"

    ####################################################
    # CARET OPTIONS MANAGEMENT
    ####################################################

    def _get_caret_options(self):
        return {
            **self._caret_options_initializer_default(),
            **(self.env[self.custom_handler_model_name]._caret_options_initializer() if self.custom_handler_model_id else {}),
        }

    def _caret_options_initializer_default(self):
        return {
            'account.account': [
                {'name': _("General Ledger"), 'action': 'caret_option_open_general_ledger'},
            ],

            'account.move': [
                {'name': _("View Journal Entry"), 'action': 'caret_option_open_record_form'},
            ],

            'account.move.line': [
                {'name': _("View Journal Entry"), 'action': 'caret_option_open_record_form', 'action_param': 'move_id'},
            ],

            'account.payment': [
                {'name': _("View Payment"), 'action': 'caret_option_open_record_form', 'action_param': 'payment_id'},
            ],

            'account.bank.statement': [
                {'name': _("View Bank Statement"), 'action': 'caret_option_open_statement_line_reco_widget'},
            ],

            'res.partner': [
                {'name': _("View Partner"), 'action': 'caret_option_open_record_form'},
            ],
        }

    def caret_option_open_record_form(self, options, params):
        model, record_id = self._get_model_info_from_id(params['line_id'])
        record = self.env[model].browse(record_id)
        target_record = record[params['action_param']] if 'action_param' in params else record

        view_id = self._resolve_caret_option_view(target_record)

        action = {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'views': [(view_id, 'form')], # view_id will be False in case the default view is needed
            'res_model': target_record._name,
            'res_id': target_record.id,
            'context': self.env.context,
        }

        if view_id is not None:
            action['view_id'] = view_id

        return action

    def _get_caret_option_view_map(self):
        return {
            'account.payment': 'account.view_account_payment_form',
            'res.partner': 'base.view_partner_form',
            'account.move': 'account.view_move_form',
        }

    def _resolve_caret_option_view(self, target):
        '''Retrieve the target view of the caret option.

        :param target:  The target record of the redirection.
        :return: The id of the target view.
        '''
        view_map = self._get_caret_option_view_map()

        view_xmlid = view_map.get(target._name)
        if not view_xmlid:
            return None

        return self.env['ir.model.data']._xmlid_lookup(view_xmlid)[1]

    def caret_option_open_general_ledger(self, options, params):
        # When coming from a specific account, the unfold must only be retained
        # on the specified account. Better performance and more ergonomic
        # as it opens what client asked. And "Unfold All" is 1 clic away.
        options["unfold_all"] = True
        general_ledger = self.env.ref('account_reports.general_ledger_report')
        account_id_to_search = self._get_res_id_from_line_id(params['line_id'], 'account.account')
        company_id_to_search = self._get_res_id_from_line_id(params['line_id'], 'res.company')
        if not account_id_to_search and not company_id_to_search:
            raise UserError(_(
                "'Open General Ledger' caret option is only available form report lines targetting "
                "accounts or Result Brought Forward."
            ))

        if account_id_to_search:
            search_content = self.env['account.account'].browse(account_id_to_search).code
        elif len(self.env.companies) == 1:
            search_content = str(UNDISTR_LINE_NAME)
        else:
            search_content = _(
                "%(line_name)s - %(company_name)s",
                line_name=UNDISTR_LINE_NAME,
                company_name=self.env['res.company'].browse(company_id_to_search).name,
            )
        gl_options = general_ledger.get_options(options)
        gl_options['not_reset_journals_filter'] = True  # prevents resetting the default journal group
        gl_options['unfold_all'] = True
        gl_options['filter_search_bar'] = search_content

        action_vals = self.env['ir.actions.actions']._for_xml_id('account_reports.action_account_report_general_ledger')
        action_vals['params'] = {
            'options': gl_options,
            'ignore_session': True,
        }
        action_vals['context'] = dict(ast.literal_eval(action_vals['context']), default_filter_accounts=search_content)

        return action_vals

    def caret_option_open_statement_line_reco_widget(self, options, params):
        model, record_id = self._get_model_info_from_id(params['line_id'])
        record = self.env[model].browse(record_id)
        if record._name == 'account.bank.statement.line':
            return record.action_open_recon_st_line()
        elif record._name == 'account.bank.statement':
            return record.action_open_bank_reconcile_widget()
        raise UserError(_("'View Bank Statement' caret option is only available for report lines targeting bank statements."))

    ####################################################
    # MISC
    ####################################################

    def _get_custom_handler_model(self):
        """ Check whether the current report has a custom handler and if it does, return its name.
            Otherwise, try to fall back on the root report.
        """
        return self.custom_handler_model_name or self.root_report_id.custom_handler_model_name or None

    def dispatch_report_action(self, options, action, action_param=None, on_sections_source=False):
        """ Dispatches calls made by the client to either the report itself, or its custom handler if it exists.
            The action should be a public method, by definition, but a check is made to make sure
            it is not trying to call a private method.
        """
        self.ensure_one()

        if on_sections_source:
            report_to_call = self.env['account.report'].browse(options['sections_source_id'])
            options["report_id"] = report_to_call.id
            return report_to_call.dispatch_report_action(options, action, action_param=action_param, on_sections_source=False)

        if self.id not in (options['report_id'], options.get('sections_source_id')):
            raise UserError(_("Trying to dispatch an action on a report not compatible with the provided options."))

        model = self
        custom_handler_model = self._get_custom_handler_model()
        if custom_handler_model and hasattr(self.env[custom_handler_model], action):
            model = self.env[custom_handler_model]
        report_method = get_public_method(model, action)
        args = [options, action_param] if action_param is not None else [options]
        return report_method(model, *args)

    def _get_custom_report_function(self, function_name, prefix):
        """ Returns a report function from its name, first checking it to ensure it's private (and raising if it isn't).
            This helper is used by custom report fields containing function names.
            The function will be called on the report's custom handler if it exists, or on the report itself otherwise.
        """
        self.ensure_one()
        function_name_prefix = f'_report_{prefix}_'
        if not function_name.startswith(function_name_prefix):
            raise UserError(_("Method '%(method_name)s' must start with the '%(prefix)s' prefix.", method_name=function_name, prefix=function_name_prefix))

        if self.custom_handler_model_id:
            handler = self.env[self.custom_handler_model_name]
            if hasattr(handler, function_name):
                return getattr(handler, function_name)

        if not hasattr(self, function_name):
            raise UserError(_("Invalid method “%s”", function_name))
        # Call the check method without the private prefix to check for others security risks.
        return getattr(self, function_name)

    def _get_lines(self, options, all_column_groups_expression_totals=None, warnings=None):
        if options['report_id'] != self.id:
            # Should never happen; just there to prevent BIG issues and directly spot them
            raise UserError(_("Inconsistent report_id in options dictionary. Options says %(options_report)s; report is %(report)s.", options_report=options['report_id'], report=self.id))

        # Necessary to ensure consistency of the data if some of them haven't been written in database yet
        self.env.flush_all()

        if warnings is not None:
            self._generate_common_warnings(options, warnings)

        # Merge static and dynamic lines in a common list
        if all_column_groups_expression_totals is None:
            all_column_groups_expression_totals = self._compute_expression_totals_for_each_column_group(
                self.line_ids.expression_ids,
                options,
                warnings=warnings,
            )

        dynamic_lines = self._get_dynamic_lines(options, all_column_groups_expression_totals, warnings=warnings)

        lines = []
        line_cache = {} # {report_line: report line dict}
        hide_if_zero_lines = self.env['account.report.line']

        # There are two types of lines:
        # - static lines: the ones generated from self.line_ids
        # - dynamic lines: the ones generated from a call to the functions referred to by self.dynamic_lines_generator
        # This loops combines both types of lines together within the lines list
        for line in self.line_ids: # _order ensures the sequence of the lines
            # Inject all the dynamic lines whose sequence is inferior to the next static line to add
            while dynamic_lines and line.sequence > dynamic_lines[0][0]:
                lines.append(dynamic_lines.pop(0)[1])

            parent_generic_id = None

            if line.parent_id:
                # Normally, the parent line has necessarily been treated in a previous iteration
                try:
                    parent_generic_id = line_cache[line.parent_id].id
                except KeyError as e:
                    raise UserError(_(
                        "Line '%(child)s' is configured to appear before its parent '%(parent)s'. This is not allowed.",
                        child=line.name, parent=e.args[0].name
                    ))

            line_dict = self._get_static_line_dict(options, line, all_column_groups_expression_totals, parent_id=parent_generic_id)
            line_cache[line] = line_dict

            if line.hide_if_zero:
                hide_if_zero_lines += line

            lines.append(line_dict)

        for _dummy, left_dynamic_line in dynamic_lines:
            lines.append(left_dynamic_line)

        # Manage growth comparison
        if options.get('column_percent_comparison') == 'growth':
            for line in lines:
                if options['comparison']['period_order'] == 'descending':
                    first_value, second_value = line.columns[0].no_format, line.columns[1].no_format
                else:
                    first_value, second_value = line.columns[1].no_format, line.columns[0].no_format

                green_on_positive = True
                model, line_id = self._get_model_info_from_id(line.id)

                if model == 'account.report.line' and line_id:
                    report_line = self.env['account.report.line'].browse(line_id)
                    compared_expression = report_line.expression_ids.filtered(
                        lambda expr: expr.label == line.columns[0].expression_label
                    )
                    green_on_positive = compared_expression.green_on_positive

                line.column_percent_comparison_data = self._compute_column_percent_comparison_data(
                    options, first_value, second_value, green_on_positive=green_on_positive, currency=line.columns[0].currency,
                )
        # Manage budget comparison
        elif options.get('column_percent_comparison') == 'budget':
            for line in lines:
                self._set_budget_column_comparisons(options, line)

        elif options.get('column_percent_comparison') == 'analytic_coverage':
            for line in lines:
                first_value, second_value = line.columns[0].no_format, line.columns[1].no_format
                line.column_percent_comparison_data = self._compute_column_percent_comparison_data(options, first_value, second_value, green_on_positive=False)

        # Manage hide_if_zero lines:
        # - If they have column values: hide them if all those values are 0 (or empty)
        # - If they don't: hide them if all their children's column values are 0 (or empty)
        # Also, hide all the children of a hidden line.
        hidden_lines_dict_ids = set()
        for line in hide_if_zero_lines:
            children_to_check = line
            current = line
            while current:
                children_to_check |= current
                current = current.children_ids

            all_children_zero = True
            hide_candidates = set()
            for child in children_to_check:
                child_line_dict_id = line_cache[child].id

                if child_line_dict_id in hidden_lines_dict_ids:
                    continue
                elif all(col.is_zero for col in line_cache[child].columns):
                    hide_candidates.add(child_line_dict_id)
                else:
                    all_children_zero = False
                    break

            if all_children_zero:
                hidden_lines_dict_ids |= hide_candidates

        lines[:] = filter(lambda x: x.id not in hidden_lines_dict_ids and x.parent_id not in hidden_lines_dict_ids, lines)

        # Create the hierarchy of lines if necessary
        if options.get('hierarchy'):
            lines = self._create_hierarchy(lines, options)

        # Clean up before generating totals, so _add_totals_below_sections doesn't create
        # a total line for a parent whose children were all hidden.
        if hidden_lines_dict_ids:
            lines = self._cleanup_empty_sections(lines)

        # Handle totals below sections for static lines
        lines = self._add_totals_below_sections(lines, options)

        # Unfold lines (static or dynamic) if necessary and add totals below section to dynamic lines
        lines = self._fully_unfold_lines_if_needed(lines, options)

        if self.allow_account_audit_status_on_lines:
            lines = self._add_account_status_on_lines(lines, options)

        self._inject_account_names_for_consolidation(lines)

        if self.custom_handler_model_id:
            lines = self.env[self.custom_handler_model_name]._custom_line_postprocessor(self, options, lines)

        if warnings is not None:
            custom_handler_name = self.custom_handler_model_name or self.root_report_id.custom_handler_model_name
            if custom_handler_name:
                self.env[custom_handler_name]._customize_warnings(self, options, all_column_groups_expression_totals, warnings)

        # Format values in columns of lines that will be displayed
        self._format_column_values(options, lines)
        self._update_line_comparison_data(options, lines)

        if options.get('export_mode') == 'print' and options.get('hide_0_lines'):
            lines = self._filter_out_0_lines(lines)
            lines = self._cleanup_empty_sections(lines)

        if options.get('export_mode') != 'file':
            self._postprocess_chatter_for_annotations(lines)

        return lines

    def format_column_values_from_client(self, options, client_lines):
        """ Format column values for display. Called via dispatch_report_action when rounding unit changes on client side."""
        rslt = []
        for client_line in client_lines:
            server_line = AccountReportLineData.from_dict(client_line)
            self._format_column_values(options, [server_line], force_format=True)
            rslt.append(server_line)

        return rslt

    def _format_column_values(self, options, line_data_list, force_format=False):
        for line_data in line_data_list:
            comparison_cell = (line_data.column_percent_comparison_data,) if line_data.column_percent_comparison_data else ()
            for column_data in chain(line_data.columns, comparison_cell):
                if column_data.name and not force_format:
                    # Columns which have already received a name are assumed to be already formatted; nothing needs to be done for them.
                    # This gives additional flexibility to custom reports, if needed.
                    continue

                if not column_data:
                    continue
                elif column_data.no_format is None:
                    # Pre-built comparison cells (e.g. '0.0%') carry a name but no value to format against.
                    continue
                elif column_data.is_zero and column_data.blank_if_zero:
                    rslt = ''
                elif options.get('export_mode') == 'file':
                    rslt = column_data.no_format or ''
                else:
                    rslt = self._format_value(
                        options,
                        column_data.no_format,
                        column_data.figure_type,
                        format_params=column_data.format_params,
                    )

                column_data.name = rslt

            # Handle the total in case of an horizontal group when there is no comparison and only one level of horizontal group
            if options.get('show_horizontal_group_total'):
                # In case the line has no formula
                if all(column.no_format is None for column in line_data.columns):
                    continue
                # In case total below section, some line don't have the value displayed
                if self.env.company.totals_below_sections and not options.get('ignore_totals_below_sections') and line_data.unfolded:
                    continue

                figure_type_is_valid = all(column.figure_type in {'float', 'integer', 'monetary'} for column in line_data.columns)
                total_value = sum(column.no_format for column in line_data.columns) if figure_type_is_valid else None
                line_data.horizontal_group_total_data = AccountReportColumnData(
                    name=self._format_value(
                        options,
                        total_value,
                        line_data.columns[0].figure_type,
                        format_params=line_data.columns[0].format_params,
                    ),
                    no_format=total_value,
                )

    def _update_line_comparison_data(self, options, lines, base_value=None):
        if options.get('column_percent_comparison') == 'report_line':

            if base_value is None:
                base_report_line_id = options['comparison']['base_report_line']['id']
                base_line = next((l for l in lines if self._get_model_info_from_id(l.id) == ('account.report.line', base_report_line_id)), None)

                if not base_line:
                    return

                base_value = base_line.columns[0].no_format

            for line in lines:
                column_data = line.columns[0]
                line.column_percent_comparison_data = self._compute_column_percent_comparison_data(
                    options,
                    column_data.no_format,
                    base_value,
                    green_on_positive=column_data.green_on_positive,
                )

    def _generate_common_warnings(self, options, warnings):
        # Display a warning if we're displaying only the data of the current company, but it's also part of a tax unit
        if options.get('available_tax_units') and options['tax_unit'] == 'company_only':
            warnings['account_reports.common_warning_tax_unit'] = {}

        report_company_ids = self.get_report_company_ids(options)
        # The _accessible_branches function will return the accessible branches from the ones that are already selected,
        # and the report_company_ids function will return the current company and its branches (that are selected) with the same VAT
        # or tax unit. Therefore, we will display the warning only when the selected companies do not have the same VAT
        # and in the context of branches.
        if self.filter_multi_company == 'tax_units' and any(accessible_branch.id not in report_company_ids for accessible_branch in self.env.company._accessible_branches()):
            warnings['account_reports.tax_report_warning_tax_id_selected_companies'] = {'alert_type': 'warning'}

        # Check whether there are unposted entries for the selected period and partner or not (if the report allows it)
        if options.get('date') and options.get('all_entries') is not None:
            domain = (
                Domain(self.env['account.move']._check_company_domain(report_company_ids))
                & Domain('state', '=', 'draft')
                & Domain('date', '<=', options['date']['date_to'])
            )
            if options.get('partner_ids'):
                domain &= (
                    Domain('partner_id', 'in', options['partner_ids'])
                    | Domain('partner_shipping_id', 'in', options['partner_ids'])
                    | Domain('commercial_partner_id', 'in', options['partner_ids'])
                )
            if self.env['account.move'].search_count(domain, limit=1):
                warnings['account_reports.common_warning_draft_in_period'] = {}

        if related_returns := self.env['account.return'].search(self._get_related_returns_domain(options)):
            submitted = all(account_return.state in ('submitted', 'paid') for account_return in related_returns)
            warnings['account_reports.common_link_account_return'] = {'submitted': submitted}

    def _fully_unfold_lines_if_needed(self, lines, options, line_ids_to_skip=None):
        def line_need_expansion(line_data):
            return line_data.unfolded and line_data.expand_function and line_data.id not in line_ids_to_skip

        if line_ids_to_skip is None:
            line_ids_to_skip = set()

        custom_unfold_all_batch_data = None

        # If it's possible to batch unfold and we're unfolding all lines, compute the batch, so that individual expansions are more efficient
        if options['unfold_all'] and self.custom_handler_model_id:
            lines_to_expand_by_function = {}
            for line_data in lines:
                if line_need_expansion(line_data):
                    lines_to_expand_by_function.setdefault(line_data.expand_function, []).append(line_data)

            custom_unfold_all_batch_data = self.env[self.custom_handler_model_name]._custom_unfold_all_batch_data_generator(self, options, lines_to_expand_by_function)

        i = 0
        while i < len(lines):
            # We iterate in such a way that if the lines added by an expansion need expansion, they will get it as well
            line_data = lines[i]
            if line_need_expansion(line_data):
                groupby = line_data.groupby
                to_insert = self._expand_unfoldable_line(
                    line_data.expand_function,
                    line_data.id,
                    groupby,
                    options,
                    line_data.horizontal_split_side,
                    unfold_all_batch_data=custom_unfold_all_batch_data,
                    ignore_load_more=bool(options.get('export_mode')),
                )
                lines = lines[:i+1] + to_insert + lines[i+1:]
            i += 1

        return lines

    def _add_account_status_on_lines(self, lines, options):
        if not options['audit']['id']:
            return lines

        accounts_to_search = set()
        for line in lines:
            model, id = self._get_model_info_from_id(line.id)
            if model == 'account.account':
                accounts_to_search.add(id)

        account_statuses = self.env['account.audit.account.status'].search_read(
            domain=[
                ('audit_id', '=', options['audit']['id']),
                ('account_id', 'in', tuple(accounts_to_search)),
            ],
            fields=['id', 'account_id', 'audit_id', 'status']
        )

        account_statuses = {
            account_status['account_id'][0]: account_status
            for account_status in account_statuses
        }

        for line in lines:
            model, id = self._get_model_info_from_id(line.id)
            if model == 'account.account' and id in account_statuses:
                line.account_status = account_statuses[id]

        return lines

    def _generate_total_below_section_line(self, section_line_data):
        rslt = section_line_data.copy()
        rslt.id = self._get_generic_line_id(None, None, parent_line_id=section_line_data.id, markup='total')
        rslt.level = section_line_data.level if section_line_data.level != 0 else 1  # Total line should not be level 0
        rslt.name = _("Total %s", section_line_data.name)
        rslt.parent_id = section_line_data.id
        rslt.unfoldable = False
        rslt.unfolded = False
        rslt.caret_options = None
        rslt.action_id = None
        rslt.page_break = False
        return rslt

    def _get_static_line_dict(self, options, line, all_column_groups_expression_totals, parent_id=None):
        line_id = self._get_generic_line_id('account.report.line', line.id, parent_line_id=parent_id)
        columns = self._build_static_line_columns(line, options, all_column_groups_expression_totals)
        groupby = line._get_groupby(options)
        has_children = (groupby and any(col.has_sublines for col in columns)) or bool(line.children_ids)

        rslt = AccountReportLineData(
            id=line_id,
            name=line.name,
            groupby=groupby,
            unfoldable=line.foldability == 'foldable' and has_children,
            unfolded=has_children and (line.foldability == 'always_unfolded' or line_id in options['unfolded_lines'] or options['unfold_all']),
            columns=columns,
            level=line.hierarchy_level,
            page_break=line.print_on_new_page,
            action_id=line.action_id.id,
            expand_function=groupby and '_report_expand_unfoldable_line_with_groupby' or None,
        )

        if line.horizontal_split_side:
            rslt.horizontal_split_side = line.horizontal_split_side

        if parent_id:
            rslt.parent_id = parent_id

        if line.code:
            rslt.code = line.code

        if options['show_debug_column']:
            column_group_totals = all_column_groups_expression_totals[0]
            # Only consider the first column group, as show_debug_column is only true if there is but one.

            engine_selection_labels = dict(self.env['account.report.expression']._fields['engine']._description_selection(self.env))
            expressions_detail = defaultdict(lambda: [])
            col_expression_to_figure_type = {
                column.get('expression_label'): column.get('figure_type') for column in options['columns']
            }
            for expression in line.expression_ids.filtered(lambda x: not x.label.startswith('_default')):
                engine_label = engine_selection_labels[expression.engine]
                figure_type = expression.figure_type or col_expression_to_figure_type.get(expression.label) or 'none'
                expressions_detail[engine_label].append((
                    expression.label,
                    {'formula': expression.formula, 'subformula': expression.subformula, 'value': self._format_value(options, column_group_totals[expression]['value'], figure_type)}
                ))

            # Sort results so that they can be rendered nicely in the UI
            for details in expressions_detail.values():
                details.sort(key=lambda x: x[0])
            sorted_expressions_detail = sorted(expressions_detail.items(), key=lambda x: x[0])

            if sorted_expressions_detail:
                try:
                    rslt.debug_popup_data = json.dumps({'expressions_detail': sorted_expressions_detail})
                except TypeError:
                    raise UserError(_(
                        'Invalid subformula in expression "%(expression)s" of line "%(line)s": %(subformula)s',
                        expression=expression.label,
                        line=expression.report_line_id.name,
                        subformula=expression.subformula,
                    ))
        return rslt

    @api.model
    def _build_static_line_columns(self, line, options, all_column_groups_expression_totals, groupby_model=None):
        fake_grouping_key = 0
        return self._build_lines_columns(
            line,
            options,
            {fake_grouping_key: all_column_groups_expression_totals},
            groupby_model,
        )[fake_grouping_key]

    @api.model
    def _build_lines_columns(self, line, options, aggregated_group_totals, groupby_model=False):
        """
            Return the list of column dicts (the data for each cell of a line) for each grouping key.

            :param line: The account.report.line

            :param options: The options dict for this report.

            :param aggregated_group_totals: A dict of the form {grouping_key: {
                                                                    col_group_index: {
                                                                        expression: {
                                                                            "value": ...,
                                                                            "sublines_info": ...}}}}
                                            grouping_key corresponds to the key from the groupby, so typically an id of the groupby model
                                            col_group_index            to the column identifier of the column group
                                            expression               to the account.report.expression
                                            value                    to the value for the expression
                                            sublines_info            to whether or not there are sublines.

            :param groupby_model: The model of the groupby

            :return: dict(grouping_key, column_dicts)
        """
        columns_per_grouping_key = defaultdict(list)

        line_id = line.id
        label_to_expr_dict = {expr.label: expr for expr in line.expression_ids if not expr.label.startswith('_default')}
        rounding_opt_pattern = re.compile(r"\Wrounding\W*=\W*(?P<rounding>\d+)")
        for col_data_dict in options['columns']:
            col_group_index = col_data_dict['column_group_index']
            label = col_data_dict['expression_label']
            expression = label_to_expr_dict.get(label, self.env['account.report.expression'])

            # Check carryover
            if carryover_expr := label_to_expr_dict.get(f'_carryover_{label}'):
                carryover_target = carryover_expr._get_carryover_target_expression(options).report_line_name if carryover_expr.carryover_target else False

            if applied_carryover_expr := label_to_expr_dict.get(f'_applied_carryover_{label}'):
                allow_carryover_audit = self.env.user.has_group('base.group_no_one')

            digits = 1
            if float_rounding_opt := options.get('float_rounding'):
                # This option key allows forcing the rounding of "float' figure type, to include more or less decimals
                digits = float_rounding_opt

            # Handle manual edition popup
            edit_popup_data = {}
            if expression.engine == 'reference' and len(options['companies']) == 1:
                edit_popup_data = {
                    'column_group_index': col_group_index,
                    'target_expression_id': expression.id,
                    'rounding': None,
                    'figure_type': expression.figure_type or col_data_dict['figure_type'],
                    'target_model': f'{expression.formula}',
                }
            elif expression.engine == 'external' and expression.subformula and len(options['companies']) == 1:
                # Compute rounding for manual values
                rounding = None
                figure_type = expression.figure_type or col_data_dict['figure_type']
                if figure_type == 'integer':
                    rounding = 0
                else:
                    if rounding_opt_match := rounding_opt_pattern.search(expression.subformula):
                        rounding = int(rounding_opt_match.group('rounding'))
                    elif figure_type == 'monetary':
                        rounding = self.env.company.currency_id.decimal_places

                if 'editable' in expression.subformula:
                    edit_popup_data = {
                        'column_group_index': col_group_index,
                        'target_expression_id': expression.id,
                        'rounding': rounding,
                        'figure_type': figure_type,
                    }

                digits = rounding

            # Handle editable financial budgets
            if (
                groupby_model == 'account.account'
                and options['column_groups'][col_group_index]['forced_options'].get('compute_budget')
                and self.env.user.has_group('account.group_account_manager')
            ):
                edit_popup_data = {
                    'column_group_index': col_group_index,
                    'target_expression_id': expression.id,
                    'rounding': self.env.company.currency_id.decimal_places,
                    'figure_type': 'monetary',
                }

            foreign_currency_expr = label_to_expr_dict.get(f'_currency_{label}')
            label_expr = False if options['export_mode'] else label_to_expr_dict.get(f'_cell_label_{label}')
            for grouping_key, group_totals in aggregated_group_totals.items():
                vals_dict_per_expr = group_totals[col_group_index]

                # Handle info popup
                info_popup_data = {}
                if carryover_expr:
                    carryover_value = vals_dict_per_expr[carryover_expr].get('value')
                    if carryover_value and not self.env.company.currency_id.is_zero(carryover_value):
                        info_popup_data['carryover'] = self._format_value(options, carryover_value, 'monetary')
                        if carryover_target:
                            info_popup_data['carryover_target'] = carryover_target
                        # If it's not set, it means the carryover needs to target the same expression
                if applied_carryover_expr:
                    applied_carryover_value = vals_dict_per_expr[applied_carryover_expr].get('value')
                    if applied_carryover_value and not self.env.company.currency_id.is_zero(applied_carryover_value):
                        info_popup_data |= {
                            'allow_carryover_audit': allow_carryover_audit,
                            'applied_carryover': self._format_value(options, applied_carryover_value, 'monetary'),
                            'expression_id': applied_carryover_expr.id,
                            'column_group_index': col_group_index,
                        }

                vals_dict = vals_dict_per_expr.get(expression, {})
                col_value = vals_dict.get('value')
                if edit_popup_data:
                    edit_popup_data['column_value'] = col_value

                currency = False
                if col_value is not None and foreign_currency_expr:  # In case column value is zero, we still want to go through the condition
                    currency = self.env['res.currency'].browse(vals_dict_per_expr[foreign_currency_expr].get('value'))

                column_data = self._build_column_data(
                    col_value,
                    col_data_dict,
                    options=options,
                    column_expression=expression if expression else None,
                    has_sublines=vals_dict.get('sublines_info'),
                    report_line_id=line_id,
                    digits=digits,
                    currency=currency,
                )

                if label_expr:
                    column_data.cell_label = vals_dict_per_expr[label_expr].get('value')

                if info_popup_data:
                    column_data.info_popup_data = json.dumps(info_popup_data)

                if edit_popup_data:
                    column_data.edit_popup_data = json.dumps(edit_popup_data)

                columns_per_grouping_key[grouping_key].append(column_data)

        return columns_per_grouping_key

    def _build_column_data(
            self, col_value, options_col_desc,
            options=None, currency=None, digits=1,
            column_expression=None, has_sublines=False,
            report_line_id=None,
    ):
        # Empty column
        if col_value is None and options_col_desc is None:
            return AccountReportColumnData()

        options_col_desc = options_col_desc or {}
        column_expression = column_expression or self.env['account.report.expression']
        options = options or {}

        blank_if_zero = column_expression.blank_if_zero or options_col_desc.get('blank_if_zero', False)
        figure_type = column_expression.figure_type or options_col_desc.get('figure_type', 'string')

        format_params = AccountReportColumnFormatParamsData()

        if figure_type == 'monetary' and currency:
            format_params.currency_id = currency.id
        elif figure_type in ('float', 'percentage'):
            format_params.digits = digits

        col_group_index = options_col_desc.get('column_group_index')

        return AccountReportColumnData(
            auditable=col_value is not None
                         and column_expression.auditable
                         and not options['column_groups'][col_group_index]['forced_options'].get('compute_budget'),
            blank_if_zero=blank_if_zero,
            column_group_index=col_group_index,
            currency=currency,
            currency_symbol=(currency or self.env.company.currency_id).symbol if options.get('multi_currency') else None,
            digits=digits,
            expression_label=options_col_desc.get('expression_label'),
            figure_type=figure_type,
            green_on_positive=column_expression.green_on_positive,
            has_sublines=has_sublines,
            is_zero=col_value is None or (
                isinstance(col_value, (int, float))
                and figure_type in NUMBER_FIGURE_TYPES
                and self._is_value_zero(col_value, figure_type, format_params)
            ),
            no_format=col_value,
            format_params=format_params,
            report_line_id=report_line_id,
            sortable=options_col_desc.get('sortable', False),
            comparison_mode=options_col_desc.get('comparison_mode'),
        )

    def _inject_account_names_for_consolidation(self, lines):
        """ When grouping by account_code, in order to make the consolidation clearer, we add the account name in the context
            of the current company next to the account_code.
        """
        account_codes = []
        for line in lines:
            markup = self._get_markup(line.id)
            if isinstance(markup, dict) and markup.get('groupby') == 'account_code':
                account_codes.append(line.name)
        if not account_codes:
            return

        account_code_to_account_name_dict = {account.code: account.name for account in self.env['account.account'].search([
            *self.env['account.account']._check_company_domain(self.env.company),
            ('code', 'in', account_codes),
        ])}
        for line in lines:
            markup = self._get_markup(line.id)
            if isinstance(markup, dict) and markup.get('groupby') == 'account_code':
                account_code = line.name
                account_name = account_code_to_account_name_dict.get(account_code)
                if account_code and account_name:
                    line.name = f'{account_code} {account_name}'

    def _get_dynamic_lines(self, options, all_column_groups_expression_totals, warnings=None):
        if self.custom_handler_model_id:
            rslt = self.env[self.custom_handler_model_name]._dynamic_lines_generator(self, options, all_column_groups_expression_totals, warnings=warnings)
            self._apply_integer_rounding_to_dynamic_lines(options, (line for _sequence, line in rslt))
            return rslt
        return []

    def _apply_integer_rounding_to_dynamic_lines(self, options, dynamic_lines):
        if options.get('integer_rounding_enabled'):
            for line in dynamic_lines:
                for column_dict in line.columns or []:
                    if not column_dict.name and column_dict.figure_type == 'monetary' and column_dict.no_format:
                        # If 'name' is already in it, no need to round the amount ; it is forced by the custom report already
                        column_dict.no_format = float_round(
                            column_dict.no_format,
                            precision_digits=0,
                            rounding_method=options['integer_rounding'],
                        )

    def _compute_expression_totals_for_each_column_group(self, expressions, options,
        groupby_to_expand=None, forced_all_column_groups_expression_totals=None, col_groups_restrict=None, include_default_vals=False, warnings=None):
        """
            Main computation function for static lines.

            :param expressions: The account.report.expression objects to evaluate.

            :param options: The options dict for this report, obtained from.get_options({}).

            :param groupby_to_expand: The full groupby string for the grouping we want to evaluate. If None, the aggregated value will be computed.
                                      For example, when evaluating a group by partner_id, which further will be divided in sub-groups by account_id,
                                      then id, the full groupby string will be: 'partner_id, account_id, id'.

            :param forced_all_column_groups_expression_totals: The expression totals already computed for this report, to which we will add the
                                                               new totals we compute for expressions (or update the existing ones if some
                                                               expressions are already in forced_all_column_groups_expression_totals). This is
                                                               a dict in the same format as returned by this function.
                                                               This parameter is for example used when adding manual values, where only
                                                               the expressions possibly depending on the new manual value
                                                               need to be updated, while we want to keep all the other values as-is.

            :param col_groups_restrict: List of column group keys of the groups to compute. Other column groups will be ignored, and will
                                        not be added to the result of this function (they can still be provided beforehand through
                                        forced_all_column_groups_expression_totals). If not provided, all colum groups will be computed.

            :return: dict(column_group_index, expressions_totals), where:
                - column group key is string identifying each column group in a unique way ; as in options['column_groups']
                - expressions_totals is a dict in the format returned by _compute_expression_totals_for_single_column_group
        """
        if groupby_to_expand and any(not expression.report_line_id._get_groupby(options) for expression in expressions):
            raise UserError(_("Trying to expand groupby results on lines without a groupby value."))

        # Group formulas for batching (when possible)
        grouped_formulas = self._group_expression_formulas(options, expressions, groupby_to_expand=groupby_to_expand, include_default_vals=include_default_vals)

        # Treat each formula batch for each column group
        all_column_groups_expression_totals = {}
        for group_index, group_options in self._split_options_per_column_group(options).items():
            if forced_all_column_groups_expression_totals:
                forced_column_group_totals = forced_all_column_groups_expression_totals.get(group_index, None)
            else:
                forced_column_group_totals = None

            if not col_groups_restrict or group_index in col_groups_restrict:
                current_group_expression_totals = self._compute_expression_totals_for_single_column_group(
                    group_options,
                    grouped_formulas,
                    forced_column_group_expression_totals=forced_column_group_totals,
                    warnings=warnings,
                )
            else:
                current_group_expression_totals = forced_column_group_totals

            all_column_groups_expression_totals[group_index] = current_group_expression_totals

        return all_column_groups_expression_totals

    def _group_expression_formulas(self, options, expressions, groupby_to_expand=None, include_default_vals=False):
        def add_expressions_to_groups(expressions_to_add, grouped_formulas, forced_date_scope=None):
            """ Groups the expressions that should be computed together.
            """
            for expression in expressions_to_add:
                engine = expression.engine if expression.engine != 'custom' else expression.formula

                if engine not in grouped_formulas:
                    grouped_formulas[engine] = {}

                if forced_date_scope:
                    date_scope = forced_date_scope
                elif expression.engine == 'aggregation':
                    date_scope = None
                else:
                    date_scope = self._standardize_date_scope_for_date_range(expression.date_scope)

                groupby_data = expression.report_line_id._parse_groupby(options, groupby_to_expand=groupby_to_expand)

                grouping_key = (date_scope, groupby_data['current_groupby'])

                if grouping_key not in grouped_formulas[engine]:
                    grouped_formulas[engine][grouping_key] = {}

                formula = re.sub(r'\s+', ' ', expression.formula.strip())

                if formula not in grouped_formulas[engine][grouping_key]:
                    grouped_formulas[engine][grouping_key][formula] = expression
                else:
                    grouped_formulas[engine][grouping_key][formula] |= expression

        grouped_formulas = {}

        if expressions and not include_default_vals:
            expressions = expressions.filtered(lambda x: not x.label.startswith('_default'))
        expressions_to_group = list(expressions)
        while expressions_to_group:
            expression = expressions_to_group.pop()
            if expression.engine == 'aggregation' and (cross_report_match := CROSS_REPORT_REGEX.match(expression.subformula or '')):
                forced_date_scope = self._standardize_date_scope_for_date_range(expression.date_scope) if cross_report_match['force_date_scope'] else None

                # Always expand aggregation expressions, in case their subexpressions are not in expressions parameter
                # (this can happen in cross report, or when auditing an individual aggregation expression)
                expanded_cross = expression._expand_aggregations()

                for expansion_res in expanded_cross:
                    if expansion_res == expression:
                        continue

                    expansion_cross_report_match = CROSS_REPORT_REGEX.match(expansion_res.subformula or '')
                    if expansion_cross_report_match:
                        if cross_report_match['force_date_scope']:
                            raise UserError(self.env._(
                                "Cross-report aggregation with forced date scope '%(label)s' of line '%(report_line)s' depends on another cross-report aggregation. This is not allowed.",
                                label=expression.label,
                                report_line=expression.report_line_id.name,
                            ))
                        if expansion_cross_report_match['force_date_scope']:
                            raise UserError(self.env._(
                                "Cross-report aggregation '%(label)s' of line '%(report_line)s' depends on another cross-report aggregation with a forced date scope. This is not allowed.",
                                label=expression.label,
                                report_line=expression.report_line_id.name,
                            ))

                add_expressions_to_groups(expanded_cross, grouped_formulas, forced_date_scope=forced_date_scope)
            elif expression.engine == 'aggregation' and groupby_to_expand:
                # Expanded expressions from cross report aggregations must be grouped using the correct date scope.
                # To achieve this, handle them separately from other aggregation expressions:
                # - Expand aggregation expressions without cross-report ones.
                # - Then add cross-report expressions to expressions_to_group list so they
                #   are expanded and grouped later with the proper date scope (see condition above).
                expanded_expressions = expression._expand_aggregations(no_cross_report_expansion=True)
                expanded_cross = expanded_expressions.filtered(lambda e: e.subformula and e.subformula.startswith('cross_report'))

                add_expressions_to_groups(expanded_expressions - expanded_cross, grouped_formulas)
                expressions_to_group.extend(expanded_cross)
            else:
                add_expressions_to_groups(expression, grouped_formulas)

        return grouped_formulas

    def _build_sum_children_formula(self, expression):
        """ Builds the formula to be used to evaluate a sum_children aggregation.
        """
        return ' + '.join(
            f'_expression:{child_expr.id}'
            for child_expr in expression.report_line_id.children_ids.expression_ids.filtered(lambda e: e.label == expression.label)
        )

    def _standardize_date_scope_for_date_range(self, date_scope):
        """ Depending on the fact the report accepts date ranges or not, different date scopes might mean the same thing.
        This function is used so that, in those cases, only one of these date_scopes' values is used, to avoid useless creation
        of multiple computation batches and improve the overall performance as much as possible.
        """
        if not self.filter_date_range and date_scope == 'strict_range':
            return 'from_beginning'
        else:
            return date_scope

    def _split_options_per_column_group(self, options):
        """ Get a specific option dict per column group, each enforcing the comparison and horizontal grouping associated
        with the column group. Each of these options dict will contain a new key 'owner_column_group', with the column group key of the
        group it was generated for.

        :param options: The report options upon which the returned options be be based.

        :return:        A dict(column_group_index, options_dict), where column_group_index is the string identifying each column group (the keys
                        of options['column_groups'], and options_dict the generated options for this group.
        """
        options_per_group = {}
        for group_index in range(len(options['column_groups'])):
            group_options = self._get_column_group_options(options, group_index)
            options_per_group[group_index] = group_options

        return options_per_group

    def _get_column_group_options(self, options, group_index):
        column_group = options['column_groups'][group_index]
        return {
            **options,
            **column_group['forced_options'],
            'forced_domain': options.get('forced_domain', []) + column_group['forced_domain'] + column_group['forced_options'].get('forced_domain', []),
            'owner_column_group': group_index,
        }

    def _compute_expression_totals_for_single_column_group(self, column_group_options, grouped_formulas, forced_column_group_expression_totals=None, warnings=None):
        """ Evaluates expressions for a single column group.

            :param column_group_options: The options dict obtained from _split_options_per_column_group() for the column group to evaluate.

            :param grouped_formulas: A dict(engine, formula_dict), where:
                                     - engine is a string identifying a report engine, in the same format as in account.report.expression's engine
                                       field's technical labels.
                                     - formula_dict is a dict in the same format as _compute_formula_batch's formulas_dict parameter,
                                       containing only aggregation formulas.

            :param forced_column_group_expression_totals: The expression totals previously computed, in the same format as this function's result.
                                                          If provided, the result of this function will be an updated version of this parameter,
                                                          recomputing the expressions in grouped_fomulas.

            :return: A dict(expression, {'value': value, 'has_sublines': has_sublines}), where:
                     - expression is one of the account.report.expressions that got evaluated

                     - value is the result of that evaluation. Two cases are possible:
                        - if we're evaluating a groupby: value will then be a in the form [(groupby_key, group_val)], where
                            - groupby_key is the key used in the SQL GROUP BY clause to generate this result
                            - group_val: The result computed by the engine for this group. Typically a float.

                        - else: value will directly be the result computed for this expression

                     - has_sublines: [optional key, will default to False if absent]
                                       Whether or not this result corresponds to 1 or more subelements in the database (typically move lines).
                                       This is used to know whether an unfoldable line has results to unfold in the UI.
        """
        def inject_formula_results(formula_results, column_group_expression_totals, cross_report_expression_totals=None):
            for expressions, result in formula_results.items():
                for expression in expressions:
                    subformula_error_format = _(
                        'Invalid subformula in expression "%(expression)s" of line "%(line)s": %(subformula)s',
                        expression=expression.label,
                        line=expression.report_line_id.name,
                        subformula=expression.subformula,
                    )
                    if expression.engine not in ('aggregation', 'external', 'reference') and expression.subformula:
                        # Those engines use their subformulas differently. They cannot be used as result keys
                        result_value_key = expression.subformula
                    else:
                        result_value_key = 'result'

                    # The expression might be signed, so we can't just access the dict key, and directly evaluate it instead.

                    if isinstance(result, list):
                        # Happens when expanding a groupby line, to compute its children.
                        # We then want to keep a list(grouping key, total) as the final result of each total
                        expression_value = []
                        sublines_info = set()
                        for key, result_dict in result:
                            if result_dict['has_sublines']:
                                sublines_info.add(key)
                            try:
                                expression_value.append((key, result_dict[result_value_key]))
                            except KeyError:
                                raise UserError(subformula_error_format)
                    else:
                        # For non-groupby lines, we directly set the total value for the line.
                        try:
                            expression_value = result[result_value_key]
                            sublines_info = result.get('has_sublines', False)
                        except KeyError:
                            raise UserError(subformula_error_format)

                    if column_group_options.get('integer_rounding_enabled'):
                        in_monetary_column = any(
                            col['expression_label'] == expression.label
                            for col in column_group_options['columns']
                            if col['figure_type'] == 'monetary'
                        )

                        if (in_monetary_column and not expression.figure_type) or expression.figure_type == 'monetary':
                            method = column_group_options['integer_rounding']
                            if isinstance(expression_value, list):
                                expression_value = [(key, float_round(value, precision_digits=0, rounding_method=method) if value is not None else value) for key, value in expression_value]
                            else:
                                expression_value = float_round(expression_value, precision_digits=0, rounding_method=method)

                    expression_result = {
                        'value': expression_value,
                        'sublines_info': sublines_info,
                    }

                    if expression.report_line_id.report_id == self:
                        if expression in column_group_expression_totals:
                            # This can happen because of a cross report aggregation referencing an expression of its own report,
                            # but forcing a different date_scope onto it. This case is not supported for now ; splitting the aggregation can be
                            # used as a workaround.
                            raise UserError(_(
                                "Expression labelled '%(label)s' of line '%(line)s' is being overwritten when computing the current report. "
                                "Make sure the cross-report aggregations of this report only reference terms belonging to other reports.",
                                label=expression.label, line=expression.report_line_id.name
                            ))

                        column_group_expression_totals[expression] = expression_result

                    elif cross_report_expression_totals is not None:
                        # Entering this else means this expression needs to be evaluated because of a cross_report aggregation
                        cross_report_expression_totals[expression] = expression_result

        # Batch each engine that can be
        column_group_expression_totals = dict(forced_column_group_expression_totals) if forced_column_group_expression_totals else {}
        cross_report_expr_totals_by_scope = {}
        for engine, engine_grouped_formulas in grouped_formulas.items():
            if engine == 'aggregation':
                # Aggregations need to be computed after all other engines. It's done below.
                continue

            for (date_scope, current_groupby), formulas_dict in engine_grouped_formulas.items():
                formula_results = self._compute_formula_batch(column_group_options, engine, date_scope, formulas_dict, current_groupby, warnings=warnings)
                inject_formula_results(
                    formula_results,
                    column_group_expression_totals,
                    cross_report_expression_totals=cross_report_expr_totals_by_scope.setdefault(date_scope, {})
                )

        # Now that everything else has been computed, resolve aggregation expressions
        # (they can't be treated as the other engines, as if we batch them per date_scope, we'll not be able
        # to compute expressions depending on other expressions with a different date scope).
        aggregations_with_date_scope = []
        for (date_scope, current_groupby), formulas_dict in grouped_formulas.get('aggregation', {}).items():
            for expressions in formulas_dict.values():
                for expression in expressions:
                    aggregations_with_date_scope.append((date_scope, current_groupby, expression))

        if aggregations_with_date_scope:
            aggregation_formula_results = self._compute_totals_no_batch_aggregation(column_group_options, aggregations_with_date_scope, column_group_expression_totals, cross_report_expr_totals_by_scope)
            inject_formula_results(aggregation_formula_results, column_group_expression_totals)

        return column_group_expression_totals

    def _compute_totals_no_batch_aggregation(self, column_group_options, aggregations_with_date_scope, other_current_report_expr_totals, other_cross_report_expr_totals_by_scope):
        """ Computes expression totals for 'aggregation' engine, after all other engines have been evaluated.

        :param column_group_options: The options for the column group being evaluated, as obtained from _split_options_per_column_group.

        :param aggregations_with_date_scope: A list of tuples (forced_date_scope, current_groupby, expression), containing only aggregation formulas.
                                            forced_date_scope will only be set for expressions whose evaluation is required by a cross-report
                                            expression with a forced date_scope. Else, it will be None.

        :param other_current_report_expr_totals: The expressions_totals obtained after computing all non-aggregation engines, for the expressions
                                                 belonging directly to self (so, not the ones referenced by a cross_report aggreation).
                                                 This is a dict in the same format as _compute_expression_totals_for_single_column_group's result
                                                 (the only difference being it does not contain any aggregation expression yet).

        :param other_cross_report_expr_totals_by_scope: A dict(forced_date_scope, expression_totals), where expression_totals is in the same form as
                                               _compute_expression_totals_for_single_column_group's result. This parameter contains the results
                                               of the non-aggregation expressions used by cross_report expressions ; they all belong to different
                                               reports than self. The forced_date_scope corresponds to the original date_scope set on the
                                               cross_report expression referencing them. The same expressions can be referenced multiple times
                                               under different date scopes.

        :return : A dict((formula, expressions), result), where result is in the form {'result': numeric_value}
                in case of groupby: A dict ((formula, expressions): [(grouping_key, {'result': value, 'has_sublines': boolean}), ...], ...)
        """
        def _check_is_float(to_test):
            try:
                float(to_test)
                return True
            except ValueError:
                return False

        def add_expression_to_maps(expression, expression_res, figure_types_cache, eval_dict, codes_map, forced_date_scope):
            """
                Process an expression and its result, updating various dictionaries with relevant information.
                Parameters:
                - expression (object): The expression object to process.
                - expression_res (dict): The result of the expression.
                - figure_types_cache (dict): {report : {label: figure_type}}.
                - eval_dict (dict): {forced_date_scope: {expression_id: value}}.
                - codes_map (dict): {report_id: {line_code: {expression_label: expression_id}}}
                - forced_date_scope: the date-scope to be enforced when evaluating cross-report aggregations; None for non-cross-report.
            """
            expr_report = expression.report_line_id.report_id
            report_default_figure_types = figure_types_cache.setdefault(expr_report, {})
            if expression.label not in report_default_figure_types:
                report_default_figure_types[expression.label] = expr_report.column_ids.filtered(lambda x: x.expression_label == expression.label).figure_type

            figure_type = expression.figure_type or figure_types_cache[expr_report][expression.label]
            value = expression_res['value']
            if figure_type == 'monetary':
                currency = self.env.company.currency_id
                if isinstance(value, list):  # groupby
                    # Custom engines can emit None to express the absence of value
                    value = [(key, currency.round(amount or 0.0)) for key, amount in value]
                else:
                    value = currency.round(value or 0.0)

            eval_dict.setdefault(forced_date_scope, {})[expression.id] = {'value': value, 'sublines_info': expression_res['sublines_info']}

            if expression.report_line_id.code:
                codes_map.setdefault(expression.report_line_id.report_id.id, {}).setdefault(expression.report_line_id.code, {})[expression.label] = expression.id

        eval_dict = {}  # {forced_date_scope: {expression_id: {'value': value, 'sublines_info': bool or dict(grouping keys having sublines)}}}
        codes_map = {}  # {report_id: {line_code: {expression_label: expression_id}}}
        figure_types_cache = {}  # {report : {label: figure_type}}

        for expression, expression_res in other_current_report_expr_totals.items():
            add_expression_to_maps(expression, expression_res, figure_types_cache, eval_dict, codes_map, None)

        for forced_date_scope, scope_expr_totals in other_cross_report_expr_totals_by_scope.items():
            for expression, expression_res in scope_expr_totals.items():
                date_scopes_to_add = [forced_date_scope]
                if forced_date_scope == self._standardize_date_scope_for_date_range(expression.date_scope):
                    # The date_scope could be forced by a cross_report aggregation, or just be the basic one used for the report
                    date_scopes_to_add.append(None)

                for date_scope_to_add in date_scopes_to_add:
                    add_expression_to_maps(expression, expression_res, figure_types_cache, eval_dict, codes_map, date_scope_to_add)

        # Complete codes_map with the uncomputed aggregation lines
        for _forced_date_scope, _current_groupby, expression in aggregations_with_date_scope:
            if expression.report_line_id.code:
                codes_map.setdefault(expression.report_line_id.report_id.id, {}).setdefault(expression.report_line_id.code, {})[expression.label] = expression.id

        # {(forced_date_scope, current_groupby, expression): count}: Number of uncomputed aggregations each of these expressions depend on
        aggregation_dependency_counts = {}
        aggregation_dependency_map = {}  # {aggregation_expr: set(depending_aggregations)}
        parsed_terms = {}  # {(expression, formula/subformula): [{'expression_id': x}, {'line_code': y, 'label': z}, ...]}
        sum_children_formula_cache = {}  # {expression: resolved sum_children formula}
        for forced_date_scope, current_groupby, expression in aggregations_with_date_scope:
            term_aggregations = self.env['account.report.expression']

            cross_report_match = CROSS_REPORT_REGEX.match(expression.subformula or '')
            if cross_report_match:
                if cross_report_match['report'].isdigit():
                    terms_report_id = int(cross_report_match['report'])
                else:
                    terms_report_id = self.env.ref(cross_report_match['report']).id
            else:
                terms_report_id = expression.report_line_id.report_id.id

            evaluation_codes_map = codes_map.get(terms_report_id, {})

            # Resolve sum_children if needed
            formula_to_parse = re.sub(r'\s+', ' ', expression.formula)
            if expression.formula == 'sum_children':
                formula_to_parse = self._build_sum_children_formula(expression)
                sum_children_formula_cache[expression] = formula_to_parse

            # Parse terms
            formula_terms = []
            for term_str in AGG_ENGINE_TERM_SEPARATOR_REGEX.split(formula_to_parse):
                if term_str and not _check_is_float(term_str):
                    if term_str.startswith('_expression:'):
                        term_expression_id = int(term_str.split(':')[1])
                    else:
                        line_code, label = term_str.split('.')
                        term_expression_id = evaluation_codes_map.get(line_code, {}).get(label)

                        if not term_expression_id and cross_report_match:
                            # For the case where a cross report expression would also reference terms in the current report
                            term_expression_id = codes_map.get(expression.report_line_id.report_id.id, {}).get(line_code, {}).get(label)

                    if not term_expression_id:
                        raise UserError(_("Unknown term '%(term)s', in aggregation formula '%(formula)s'", term=term_str, formula=formula_to_parse))

                    formula_terms.append({'expression_id': term_expression_id, 'unparsed': term_str})

                    term_expression = self.env['account.report.expression'].browse(term_expression_id)  # Should be in cache already
                    if term_expression.engine == 'aggregation':
                        term_aggregations |= term_expression

            parsed_terms[expression, formula_to_parse] = formula_terms

            # Parse bounds depending on other expressions
            if expression.subformula and expression.subformula.startswith('if_other_expr_'):
                other_expr_criterium_match = AGG_ENGINE_BOUND_CRITERIUM_REGEX.match(expression.subformula)
                if not other_expr_criterium_match:
                    raise UserError(_("Wrong format for if_other_expr_above/if_other_expr_below formula: %s", expression.subformula))

                criterium_code = other_expr_criterium_match['line_code']
                criterium_label = other_expr_criterium_match['expr_label']

                bound_expression_id = evaluation_codes_map.get(criterium_code, {}).get(criterium_label)
                if not bound_expression_id:
                    raise UserError(_("This subformula references an unknown expression: %s", expression.subformula))

                parsed_terms[expression, expression.subformula] = [{
                    'expression_id': bound_expression_id,
                    'unparsed': expression.subformula,
                    'bound_criterium': other_expr_criterium_match['criterium'],
                    'bound_params': other_expr_criterium_match['bound_params'],
                }]

                bound_expression = self.env['account.report.expression'].browse(bound_expression_id)
                if bound_expression.engine == 'aggregation':
                    term_aggregations |= bound_expression

            aggregation_dependency_counts[forced_date_scope, current_groupby, expression] = len(term_aggregations)

            # Add the current expression as a dependency of all its terms
            for expr_term_expression in term_aggregations:
                aggregation_dependency_map.setdefault(expr_term_expression, set()).add(expression)

        # Aggregations without dependency to other aggregations can directly be computed
        to_treat = [key for key, count in aggregation_dependency_counts.items() if not count]  # [(forced_date_scope, expression)]

        # Compute aggregations
        rslt = {}
        while to_treat:
            forced_date_scope, current_groupby, expression = to_treat.pop()
            date_scope_eval_dict = eval_dict.get(forced_date_scope, {})

            formula_result, sublines_info = self._aggregation_compute_formula_result(column_group_options, expression, current_groupby, date_scope_eval_dict, parsed_terms, sum_children_formula_cache)

            # Reduce dependency counter for aggregations depending on the newly-computed aggregation
            for depending_expr in aggregation_dependency_map.get(expression, []):
                if depending_expr.report_line_id.report_id == self and not CROSS_REPORT_REGEX.match(depending_expr.subformula or ''):
                    # Can happen when a regular aggregation references a cross-report aggregation with a forced date_scope.
                    # In this case, the expression will be computed with a forced date_scope, but the aggregation depending on it
                    # will expect a None date_scope in the key.
                    dependency_key = (None, current_groupby, depending_expr)
                else:
                    dependency_key = (forced_date_scope, current_groupby, depending_expr)

                if dependency_key in aggregation_dependency_counts:
                    aggregation_dependency_counts[dependency_key] -= 1

                    # If the dependency counter is 0, it means the aggregation can now be resolved, in a following iteration
                    if aggregation_dependency_counts[dependency_key] == 0:
                        to_treat.append(dependency_key)

            # Store result
            if expression.report_line_id.report_id == self:
                # This condition ensures we don't return necessary subcomputations in the final result
                if current_groupby:
                    rslt[expression] = [
                        (grouping_key, {
                            'result': value,
                            'has_sublines': grouping_key in sublines_info,
                        }) for grouping_key, value in formula_result
                    ]
                else:
                    rslt[expression] = {'result': formula_result, 'has_sublines': sublines_info}

            # Handle recursive aggregations (explicit or through the sum_children shortcut).
            # We need to make the result of our computation available to other aggregations, as they are still waiting in to_treat to be evaluated.
            eval_dict.setdefault(forced_date_scope, {})[expression.id] = {'value': formula_result, 'sublines_info': sublines_info}

            if forced_date_scope and expression.report_line_id.report_id == self:
                # In case a cross-report expression with a forced date_scope is evaluated for the current report, we want its result
                # to also be available to the regular aggregations of the current report, without any forced_date_scope
                eval_dict.setdefault(None, {})[expression.id] = {'value': formula_result, 'sublines_info': sublines_info}

        # If there are still elements with unresolved dependencies, it means they can't be evaluated, likely due to cyclic dependencies
        if any(count != 0 for count in aggregation_dependency_counts.values()):
            raise UserError(_("Not all aggregation expressions could be computed. This is likely due to cyclic dependencies in their formulas."))

        return rslt

    def _aggregation_compute_formula_result(self, col_group_options, expression, current_groupby, date_scope_eval_dict, parsed_terms, sum_children_formula_cache):

        if expression.id in date_scope_eval_dict:
            expression_res = date_scope_eval_dict[expression.id]
            return expression_res['value'], expression_res['sublines_info']

        term_replacement_regex = r"(^|(?<=[ ()+/*-]))%s((?=[ ()+/*-])|$)"
        mutated_formula = re.sub(r'\s+', ' ', expression.formula) if expression.formula != 'sum_children' else sum_children_formula_cache[expression]

        if current_groupby:
            # Collect values for each term and gather all group keys while preserving the order returned by
            # each term's engine (e.g. move lines are chronological, and cumulative columns depend on it).
            term_values = {}  # {unparsed_term_str: {grouping_key: value}}
            all_group_keys = {}  # Used as an ordered set
            sublines_info = set()
            for term in parsed_terms[expression, mutated_formula]:
                try:
                    expression_res = date_scope_eval_dict[term['expression_id']]
                    term_val = expression_res['value']
                    sublines_info.update(expression_res['sublines_info'])
                except KeyError:
                    raise UserError(_(
                        "Could not resolve term %(term)s while evaluating formula %(unresolved_formula)s",
                        term=term['unparsed'],
                        unresolved_formula=expression.formula,
                    ))
                term_dict = dict(term_val)
                term_values[term['unparsed']] = term_dict
                all_group_keys.update(dict.fromkeys(term_dict))

            # Evaluate formula for each group key
            formula_result = []
            for group_key in all_group_keys:
                key_formula = mutated_formula
                for term_str, term_val in term_values.items():
                    val = term_val.get(group_key, 0.0)
                    key_formula = re.sub(term_replacement_regex % re.escape(term_str), str(val), key_formula)
                try:
                    key_result = expr_eval(key_formula)
                except ZeroDivisionError:
                    if expression.subformula != "ignore_zero_division":
                        raise UserError(_(
                            "Division by zero occurred while evaluating Expression: %(line_name)s > %(label)s with group by %(group_by)s.",
                            line_name=expression.report_line_name,
                            label=expression.label,
                            group_by=current_groupby,
                        ))
                    key_result = 0
                formula_result.append((group_key, key_result))
        else:
            sublines_info = False
            # Replace every subterm in the formula with its value from the eval_dict
            for term in parsed_terms[expression, mutated_formula]:
                try:
                    expression_res = date_scope_eval_dict[term['expression_id']]
                    term_value = expression_res['value']
                    sublines_info = sublines_info or expression_res['sublines_info']
                except KeyError:
                    raise UserError(_(
                        "Could not resolve term %(term)s while evaluating formula %(unresolved_formula)s",
                        term=term['unparsed'],
                        unresolved_formula=expression.formula,
                    ))
                mutated_formula = re.sub(term_replacement_regex % re.escape(term['unparsed']), str(term_value), mutated_formula)

            # Everything subterm has been replaced in mutated_formula ; evaluate it
            try:
                formula_result = expr_eval(mutated_formula)
            except ZeroDivisionError:
                if expression.subformula != "ignore_zero_division":
                    raise UserError(_(
                        "Division by zero occurred while evaluating Expression: %(line_name)s > %(label)s.",
                        line_name=expression.report_line_name,
                        label=expression.label,
                    ))
                # Arbitrary choice; for clarity of the report. A 0 division could typically happen when there is no result in the period.
                formula_result = 0

        # Apply bounds if needed
        if expression.subformula and expression.subformula.startswith('if_other_expr_'):
            bound_term = parsed_terms[expression, expression.subformula][0]
            criterium_val = date_scope_eval_dict[bound_term['expression_id']]['value']

            # When groupby, the criterium value is checked on the total
            if current_groupby:
                criterium_val = sum(val for _key, val in criterium_val)

            bound_subformula = bound_term['bound_criterium'].replace('other_expr_', '')  # e.g. 'if_other_expr_above' => 'if_above'
            bound_params = bound_term['bound_params']
            bounded_value = self._aggregation_apply_bounds(col_group_options, f"{bound_subformula}({bound_params})", criterium_val)
            if current_groupby:
                formula_result = formula_result if bounded_value is not None else []
                sublines_info = sublines_info if bounded_value is not None else {}
            else:
                formula_result *= int(bool(bounded_value is not None))
                sublines_info = sublines_info and bounded_value is not None
        else:
            bounded_value = self._aggregation_apply_bounds(col_group_options, expression.subformula, formula_result, current_groupby)
            if current_groupby:
                formula_result = bounded_value or []
                sublines_info = sublines_info if bounded_value is not None else {}
            else:
                formula_result = bounded_value or 0
                sublines_info = sublines_info and bounded_value is not None

        # Handle integer rounding
        if col_group_options.get('integer_rounding_enabled'):
            rounding_method = col_group_options['integer_rounding']
            if current_groupby:
                formula_result = [
                    (key, float_round(value, precision_digits=0, rounding_method=rounding_method))
                    for key, value in formula_result
                ]
            else:
                formula_result = float_round(formula_result, precision_digits=0, rounding_method=rounding_method)

        return formula_result, sublines_info

    def _aggregation_apply_bounds(self, column_group_options, subformula, unbounded_value, current_groupby=None):
        """ Applies the bounds of the provided aggregation expression to an unbounded value that got computed for it and returns the result.
        Bounds can be defined as subformulas of aggregation expressions, with the following possible values:

            - if_above(CUR(bound_value)):
                                    => Result will be None if it's <= the provided bound value; else it'll be unbounded_value

            - if_below(CUR(bound_value)):
                                    => Result will be None if it's >= the provided bound value; else it'll be unbounded_value

            - if_between(CUR(bound_value1), CUR(bound_value2)):
                                    => Result will be None if it isn't strictly between the provided bound values; else it'll be unbounded_value

            - round(decimal_places, rounding_method):
                                    => Result will be the rounded unbounded_value.

            (where CUR is a currency code, and bound_value* are float amounts in CUR currency)

        When current_groupby is set, unbounded_value is a list of (grouping_key, value) tuples:
            - For 'round': rounding is applied to each individual value.
            - 'bound' check is not applied with groupby
        """
        def _apply_round(value, precision_string, rounding_method):
            # We support rounding with a negative amount, similarly to how it works with python's round method.
            # As we also want to support using a rounding method, we will play a bit with the number and round using float_round
            if precision_string < 0:
                precision_power = abs(precision_string)
                value /= 10 ** precision_power
                value = float_round(value, precision_digits=0, rounding_method=rounding_method)
                return value * (10 ** precision_power)
            return float_round(value, precision_digits=precision_string, rounding_method=rounding_method)

        if not subformula:
            return unbounded_value

        # So an expression can't have bounds and be cross_reports, for simplicity.
        # To do that, just split the expression in two parts.
        if subformula and subformula.startswith('round'):
            matches = re.match(r"round\((?P<precision>-?\d+)(,\s*(?P<rounding_method>(HALF-UP|HALF-DOWN|HALF-EVEN|UP|DOWN)))?\)", subformula)
            precision_string = int(matches['precision'])
            rounding_method = matches['rounding_method'] or 'HALF-DOWN'

            if current_groupby:
                return [(key, _apply_round(val, precision_string, rounding_method)) for key, val in unbounded_value]
            return _apply_round(unbounded_value, precision_string, rounding_method)

        if subformula != 'ignore_zero_division' and not subformula.startswith('cross_report'):
            company_currency = self.env.company.currency_id
            date_to = column_group_options['date']['date_to']

            match = re.match(
                r"(?P<criterium>\w*)"
                r"\((?P<currency_1>[A-Z]{3})\((?P<amount_1>[-]?\d+(\.\d+)?)\)"
                r"(,(?P<currency_2>[A-Z]{3})\((?P<amount_2>[-]?\d+(\.\d+)?)\))?\)$",
                subformula.replace(' ', '')
            )
            group_values = match.groupdict()

            # Convert the provided bounds into company currency
            currency_code_1 = group_values.get('currency_1')
            currency_code_2 = group_values.get('currency_2')
            currency_codes = [
                currency_code
                for currency_code in [currency_code_1, currency_code_2]
                if currency_code and currency_code != company_currency.name
            ]

            if currency_codes:
                currencies = self.env['res.currency'].with_context(active_test=False).search([('name', 'in', currency_codes)])
            else:
                currencies = self.env['res.currency']

            amount_1 = float(group_values['amount_1'] or 0)
            amount_2 = float(group_values['amount_2'] or 0)
            for currency in currencies:
                if currency != company_currency:
                    if currency.name == currency_code_1:
                        amount_1 = currency._convert(amount_1, company_currency, self.env.company, date_to)
                    if amount_2 and currency.name == currency_code_2:
                        amount_2 = currency._convert(amount_2, company_currency, self.env.company, date_to)

            # For groupby, we don't apply bounds
            if current_groupby:
                return unbounded_value

            # Evaluate result
            criterium = group_values['criterium']
            if criterium == 'if_below':
                if company_currency.compare_amounts(unbounded_value, amount_1) >= 0:
                    return None
            elif criterium == 'if_above':
                if company_currency.compare_amounts(unbounded_value, amount_1) <= 0:
                    return None
            elif criterium == 'if_between':
                if company_currency.compare_amounts(unbounded_value, amount_1) < 0 or company_currency.compare_amounts(unbounded_value, amount_2) > 0:
                    return None
            else:
                raise UserError(_("Unknown bound criterium: %s", criterium))

        return unbounded_value

    def _compute_formula_batch(self, column_group_options, engine, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Evaluates a batch of formulas.

        :param column_group_options: The options for the column group being evaluated, as obtained from _split_options_per_column_group.

        :param engine: A string identifying a report engine. Must be one of account.report.expression's engine field's technical labels,
                       or the function name of a custom engine.

        :param date_scope: The date_scope under which to evaluate the fomulas. Must be one of account.report.expression's date_scope field's
                           technical labels.

        :param formulas_dict: A dict in the dict(formula, expressions), where:
                                - formula: a formula to be evaluated with the engine referred to by parent dict key
                                - expressions: a recordset of all the expressions to evaluate using formula (possibly with distinct subformulas)

        :param current_groupby: The groupby to evaluate, or None if there isn't any. In case of multi-level groupby, only contains the element
                                that needs to be computed (so, if unfolding a line doing 'partner_id,account_id,id'; current_groupby will only be
                                'partner_id').

        :param warnings: If set, must be a dict to populate with the warnings computed during the computation of this engine. If None, warnings
                         won't be computed at all.
                         The populated data will consist of warning Qweb templates' xmlids to display on the report as keys. The values will be
                         dict objects, potentially populated with the 'alert_type' key, to change the style of the warning in the UI, and the 'args'
                         key, to pass additional parameters to the template when rendering it.

        :return: The result might have two different formats depending on the situation:
            - if we're computing a groupby: {(formula, expressions): [(grouping_key, {'result': value, 'has_sublines': boolean}), ...], ...}
            - if we're not: {(formula, expressions): {'result': value, 'has_sublines': boolean}, ...}
            'result' key is the default; different engines might use one or multiple other keys instead, depending of the subformulas they allow
            (e.g. 'sum', ...)
        """
        engine_function = self._get_custom_report_function(self._get_engine_function_name(engine), 'engine')
        return engine_function(column_group_options, date_scope, formulas_dict, current_groupby, warnings=warnings)

    def _get_engine_function_name(self, engine):
        if any(engine == standard_engine for standard_engine, _name in self.env['account.report.expression']._fields['engine'].selection if standard_engine != 'custom'):
            return f'_report_engine_{engine}'
        return engine

    def _report_engine_text(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        rslt = {}
        for formula, expressions in formulas_dict.items():
            for expression in expressions:
                rslt[expression] = [] if current_groupby else {'result': expression.formula, 'has_sublines': False}
        return rslt

    @snapshotable_engine(result_aggregators={'result': sum, 'has_sublines': max})
    def _report_engine_tax_tags(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Report engine.

        The formulas made for this report simply consist of a tag label. When an expression using this engine is created, it also creates one
        account.account.tag object, where the tag name is the chosen formula striped of the sign. The balance of the expressions using this engine is
        computed by gathering all the move lines using their tags, and applying the sign of their tag to their balance.

        This engine does not support any subformula.
        """
        if current_groupby:
            self._check_groupby_fields([current_groupby])
        all_expressions = self.env['account.report.expression']
        for expressions in formulas_dict.values():
            all_expressions |= expressions
        tags = all_expressions._get_matching_tags()

        query = self._get_report_query(options, date_scope)
        groupby_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query) if current_groupby else None
        acc_tag_name = self.with_context(lang='en_US').env['account.account.tag']._field_to_sql('acc_tag', 'name')
        sql = SQL(
            """
            SELECT
                %(acc_tag_name)s AS formula,
                SUM(%(balance_select)s) AS balance,
                COUNT(account_move_line.id) AS aml_count
                %(select_groupby_sql)s

            FROM %(table_references)s

            JOIN account_account_tag_account_move_line_rel aml_tag
                ON aml_tag.account_move_line_id = account_move_line.id
            JOIN account_account_tag acc_tag
                ON aml_tag.account_account_tag_id = acc_tag.id

            WHERE %(search_condition)s
              AND aml_tag.account_account_tag_id IN %(tag_ids)s

            GROUP BY %(groupby_clause)s

            ORDER BY %(groupby_clause)s
            """,
            acc_tag_name=acc_tag_name,
            balance_select=query.table.consolidation_balance,
            select_groupby_sql=SQL(', %s AS grouping_key', groupby_sql) if groupby_sql else SQL(),
            table_references=query.from_clause,
            tag_ids=tuple(tags.ids),
            search_condition=query.where_clause,
            groupby_clause=SQL(
                "%(acc_tag_name)s %(groupby_sql)s",
                acc_tag_name=acc_tag_name,
                groupby_sql=SQL(', %s', groupby_sql) if groupby_sql else SQL(),
            ),
        )

        rslt = {
            formula_expr: [] if current_groupby else {'result': 0, 'has_sublines': False}
            for formula_expr in formulas_dict.values()
        }
        for tax_tag, balance, aml_count, *grouping_key in self.env.execute_query(sql):
            if expression := formulas_dict.get(f'-{tax_tag}'):
                balance *= -1
            else:
                expression = formulas_dict[tax_tag]
            rslt_dict = {'result': balance, 'has_sublines': aml_count > 0}
            if current_groupby:
                rslt[expression].append((grouping_key[0], rslt_dict))
            else:
                rslt[expression] = rslt_dict

        return rslt

    @snapshotable_engine(result_aggregators={'sum': sum, '-sum': sum, 'has_sublines': max})
    def _report_engine_domain(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Report engine.

        Formulas made for this engine consist of a domain on account.move.line. Only those move lines will be used to compute the result.

        This engine supports two subformulas:
        - sum: the result will be sum of the matched move lines' balances
        - -sum: the result will be the negative sum of the matched move lines' balances

        """
        def _format_result_depending_on_groupby(formula_rslt):
            if not current_groupby:
                if formula_rslt:
                    # There should be only one element in the list; we only return its totals (a dict) ; so that a list is only returned in case
                    # of a groupby being unfolded.
                    return formula_rslt[0][1]
                else:
                    # No result at all
                    return {
                        'sum': 0,
                        '-sum': 0,
                        'has_sublines': False,
                    }
            return formula_rslt

        if current_groupby:
            self._check_groupby_fields([current_groupby])

        batchable_domains_data = {}  # In the form {(model name, aml_field):  [(domain, expressions)]}
        non_batchable_domains_data = []  # In the form [(domain, expressions)]
        for formula, expressions in formulas_dict.items():
            try:
                domain = literal_eval(formula)
            except (ValueError, SyntaxError):
                raise UserError(_(
                    'Invalid domain formula in expression "%(expression)s" of line "%(line)s": %(formula)s',
                    expression=expressions[0].label,
                    line=expressions[0].report_line_id.name,
                    formula=formula,
                ))

            aml_root_fields = set()
            traversing_model_domain = []
            for term in domain:
                match term:
                    case (aml_field_expr, operator, value):
                        aml_field, _dot, model_field_expr = aml_field_expr.partition('.')
                        aml_root_fields.add(aml_field)
                        traversing_model_domain.append((model_field_expr or 'id', operator, value))
                    case str():
                        traversing_model_domain.append(term)

            if len(aml_root_fields) == 1:
                aml_field = self.env['account.move.line']._fields[next(iter(aml_root_fields))]
                if aml_field.type == 'many2one':
                    batchable_domains_data.setdefault((aml_field.comodel_name, aml_field.name), []).append((traversing_model_domain, formula, expressions))
                else:
                    non_batchable_domains_data.append((domain, formula, expressions))
            else:
                non_batchable_domains_data.append((domain, formula, expressions))

        rslt = {}
        for (batch_model, batch_aml_field), batch_domains in chain(batchable_domains_data.items(), (((None, None), [data]) for data in non_batchable_domains_data)):
            aml_domain = batch_domains[0][0] if not batch_model else None  # batch_domains contains only one element if there is not batch_model/batch_aml_field
            query = self._get_report_query(options, date_scope, domain=aml_domain)

            groupby_sql = query.table[current_groupby] if current_groupby else None
            batch_groupby_sql = query.table[batch_aml_field] if batch_aml_field else None

            query.groupby = SQL(',').join(groupby_term for groupby_term in (groupby_sql, batch_groupby_sql) if groupby_term)
            query.order = groupby_sql or SQL()
            all_query_res = self.env.execute_query_dict(query.select(*filter(None, (
                SQL('COALESCE(SUM(%s), 0.0) AS sum', query.table.consolidation_balance),
                SQL('COUNT(1) > 0 AS has_sublines'),
                SQL('%s AS grouping_key', groupby_sql) if groupby_sql else SQL(),
                SQL('%s AS batch_grouping_key', batch_groupby_sql) if batch_groupby_sql else SQL()
            ))))

            results_by_batch_grouping_key = {}
            if batch_model:
                for query_res in all_query_res:
                    results_by_batch_grouping_key.setdefault(query_res['batch_grouping_key'], []).append(query_res)

            for domain, formula, expressions in batch_domains:
                formula_rslt = []
                totals_by_grouping_key = {}

                batch_included_ids = self.env[batch_model].with_context(active_test=False).search(domain).ids if batch_model else [None]
                for batch_included_id in batch_included_ids:
                    batch_res = results_by_batch_grouping_key.get(batch_included_id, []) if batch_included_id is not None else all_query_res

                    for query_res in batch_res:
                        totals = totals_by_grouping_key.setdefault(query_res.get('grouping_key'), {
                            'sum': 0,
                            '-sum': 0,
                            'has_sublines': False,
                        })

                        res_sum = query_res['sum']
                        totals['sum'] += res_sum
                        totals['-sum'] -= res_sum
                        totals['has_sublines'] = totals['has_sublines'] or bool(query_res['has_sublines'])

                for grouping_key, totals in totals_by_grouping_key.items():
                    formula_rslt.append((grouping_key, totals))

                for expression in expressions:
                    rslt[expression] = _format_result_depending_on_groupby(formula_rslt)

        return rslt

    def _report_engine_account_codes(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        r""" Report engine.

        Formulas made for this engine target account prefixes. Each of the prefix used in the formula will be evaluated as the sum of the move
        lines made on the accounts matching it. Those prefixes can be used together with arithmetic operations to perform them on the obtained
        results.
        Example: '123 - 456' will substract the balance of all account starting with 456 from the one of all accounts starting with 123.

        It is also possible to exclude some subprefixes, with \ operator.
        Example: '123\(1234)' will match prefixes all accounts starting with '123', except the ones starting with '1234'

        To only match the balance of an account is it's positive (debit) or negative (credit), the letter D or C can be put just next to the prefix:
        Example '123D': will give the total balance of accounts starting with '123' if it's positive, else it will be evaluated as 0.

        Multiple subprefixes can be excluded if needed.
        Example: '123\(1234,1236)

        All these syntaxes can be mixed together.
        Example: '123D\(1235) + 56 - 416C'

        Note: if C or D character needs to be part of the prefix, it is possible to differentiate them of debit and credit match characters
        by using an empty prefix exclusion.
        Example 1: '123D\' will take the total balance of accounts starting with '123D'
        Example 2: '123D\C' will return the balance of accounts starting with '123D' if it's negative, 0 otherwise.
        """
        if current_groupby:
            self._check_groupby_fields([current_groupby])

        subengine_result = self._report_engine_account_codes_subengine(options, date_scope, formulas_dict, current_groupby, warnings=warnings)

        account_totals_cache = {}
        rslt = {}
        for expressions in formulas_dict.values():
            rslt_destination = rslt.setdefault(expressions, [] if current_groupby else {'result': 0, 'has_sublines': False})
            rslt_groups_by_grouping_keys = {}

            expression_results = subengine_result[expressions]

            # Manage balance_character.
            for (grouping_key, account_id), group_val in expression_results:
                if (account_total_value := account_totals_cache.get(account_id)) is None:
                    account_total_value = sum(gv['sum'] for (_gk, acc_id), gv in expression_results if acc_id == account_id)
                    account_totals_cache[account_id] = account_total_value

                comparator = self.env.company.currency_id.compare_amounts(account_total_value, 0.0)

                for multiplicator, balance_character in group_val['impact']:
                    if not balance_character or (balance_character == 'D' and comparator >= 0) or (balance_character == 'C' and comparator < 0):
                        impact_result = group_val['sum'] * multiplicator
                        if not current_groupby:
                            rslt_destination['result'] += impact_result
                            rslt_destination['has_sublines'] |= group_val['has_sublines']
                        elif grouping_key in rslt_groups_by_grouping_keys:
                            # Will happen if the same grouping key is used on move lines with different accounts.
                            # This comes from the GROUPBY in the SQL query, which uses both grouping key and account.
                            # When this happens, we want to aggregate the results of each grouping key, to avoid duplicates in the end result.
                            already_treated_rslt_group = rslt_groups_by_grouping_keys[grouping_key]
                            already_treated_rslt_group['has_sublines'] |= group_val['has_sublines']
                            already_treated_rslt_group['result'] += impact_result
                        else:
                            new_rslt_element = {'result': impact_result, 'has_sublines': group_val['has_sublines']}
                            rslt_groups_by_grouping_keys[grouping_key] = new_rslt_element
                            rslt_destination.append((grouping_key, new_rslt_element))

        if current_groupby:
            # For the load_more feature, ensure the engine's result are all sorted in a consistent way
            for results_list in rslt.values():
                results_list.sort(key=lambda x: (x[0] is None, x[0]))

        return rslt

    @snapshotable_engine(result_aggregators={'sum': sum, 'impact': min, 'has_sublines': max}, sub_engine_of='_report_engine_account_codes', version=2)
    def _report_engine_account_codes_subengine(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Subengine of account_codes ; shoudln't be used separately. It always returns its results as a list, as if it was the result of a
        groupby computation, whatever the values of current_groupby.
        """
        if current_groupby:
            self._check_groupby_fields([current_groupby])

        prefix_details_by_formula, accounts_prefix_map = self._parse_account_code_engine_formulas(options, formulas_dict)

        # Run main query
        query = self._get_report_query(options, date_scope)

        current_groupby_aml_sql = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, query) if current_groupby else None
        extra_groupby_sql = SQL(", %s", current_groupby_aml_sql) if current_groupby_aml_sql else SQL()
        extra_select_sql = SQL(", %s AS grouping_key", current_groupby_aml_sql) if current_groupby_aml_sql else SQL()

        query = SQL(
            """
            SELECT
                account_move_line.account_id AS account_id,
                SUM(%(balance_select)s) AS sum,
                COUNT(account_move_line.id) AS aml_count
                %(extra_select_sql)s
            FROM %(table_references)s
            WHERE %(search_condition)s
            GROUP BY account_move_line.account_id%(extra_groupby_sql)s
            %(order_by_sql)s
            """,
            balance_select=query.table.consolidation_balance,
            extra_select_sql=extra_select_sql,
            table_references=query.from_clause,
            search_condition=query.where_clause,
            extra_groupby_sql=extra_groupby_sql,
            order_by_sql=SQL('ORDER BY %s', current_groupby_aml_sql) if current_groupby_aml_sql else SQL(),
        )
        self.env.cr.execute(query)

        # Parse result
        res_by_prefix_account_id = {}
        for query_res in self.env.cr.dictfetchall():
            # Done this way so that we can run similar code for groupby and non-groupby
            grouping_key = query_res['grouping_key'] if current_groupby else None
            account_id = query_res['account_id']
            for prefix_key in accounts_prefix_map[account_id]:
                res_by_prefix_account_id.setdefault(prefix_key, {})\
                                        .setdefault(account_id, [])\
                                        .append((grouping_key, {
                                            'sum': query_res['sum'],
                                            'has_sublines': query_res['aml_count'] > 0,
                                        }))

        rslt = {}
        for formula, prefix_details in prefix_details_by_formula.items():
            formula_rslt_list = rslt.setdefault(formulas_dict[formula], [])

            impact_map = {}  # {(prefix_key, account_id): [(multiplicator, balance_character)]}
            for prefix_key, prefix_key_impact in prefix_details.items():
                res_by_account_id = res_by_prefix_account_id.get(prefix_key, {})

                for account_id, account_res_list in res_by_account_id.items():
                    impact_map.setdefault((prefix_key, account_id), [])
                    impact_map[prefix_key, account_id] += prefix_key_impact

            for (prefix_key, account_id), impact in impact_map.items():
                for grouping_key, grouped_account_res in res_by_prefix_account_id[prefix_key][account_id]:
                    formula_rslt_list.append((
                        (grouping_key, account_id),
                        {
                            **grouped_account_res,
                            'impact': impact,
                        }
                    ))

        return rslt

    def _parse_account_code_engine_formulas(self, options, formulas_dict):
        prefilter = self.env['account.account']._check_company_domain(self.get_report_company_ids(options))

        all_accounts = self.env['account.account'].with_context(active_test=False).search([*prefilter])
        accounts = []

        for account in all_accounts:
            account_code = account.code
            if not account_code:
                for company in account.company_ids:
                    account_code = account.with_company(company).code
                    if account_code:
                        break
            accounts.append({
                'id': account.id,
                'code': account_code,
                'tag_ids': account.tag_ids.ids,
            })

        accounts.sort(key=lambda acc: acc['code'] or '')
        tags_map = defaultdict(list)
        for acc in accounts:
            # If an account has no tags, map it to the pseudo-tag `False` such
            # that a ref which does not exist matches it, otherwise DK balance
            # fails in `test_generate_all_export_files`
            for tag in (acc['tag_ids'] or [False]):
                tags_map[tag].append(acc)

        accounts_prefix_map = defaultdict(set)
        # Gather the account code prefixes to compute the total from
        prefix_details_by_formula = {}  # in the form {formula: {prefix: [(multiplicator, balance_character]}}
        for formula in formulas_dict:
            prefix_details_by_formula[formula] = {}
            for token in filter(None, ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula.replace(' ', ''))):
                token_match = ACCOUNT_CODES_ENGINE_TERM_REGEX.match(token)

                if not token_match:
                    raise UserError(_("Invalid token '%(token)s' in account_codes formula '%(formula)s'", token=token, formula=formula))

                multiplicator = -1 if token_match['sign'] == '-' else 1
                excluded_prefixes_match = token_match['excluded_prefixes']
                excluded_prefixes = tuple(excluded_prefixes_match.split(',')) if excluded_prefixes_match else ()
                prefix = token_match['prefix']

                # We group using both prefix and excluded_prefixes as keys, for the case where two expressions would
                # include the same prefix, but exlcude different prefixes (example 104\(1041) and 104\(1042))
                prefix_key = (prefix, *excluded_prefixes)
                prefix_details_by_formula[formula].setdefault(prefix_key, []).append((multiplicator, token_match['balance_character']))

                if tag := ACCOUNT_CODES_ENGINE_TAG_ID_PREFIX_REGEX.match(prefix):
                    if tag['ref']:
                        tag_id = self.env['ir.model.data']._xmlid_to_res_id(tag['ref'])
                    else:
                        tag_id = int(tag['id'])
                    accs = tags_map[tag_id]
                else:
                    idx = bisect.bisect_left(accounts, prefix, key=lambda acc: acc['code'] or '')
                    accs = itertools.takewhile(
                        lambda acc: (acc['code'] or '').startswith(prefix),
                        itertools.islice(accounts, idx, None),
                    )

                for account in accs:
                    if excluded_prefixes and account['code'].startswith(excluded_prefixes):
                        continue
                    accounts_prefix_map[account['id']].add(prefix_key)

        return prefix_details_by_formula, accounts_prefix_map

    def _report_engine_external(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        """ Report engine.

        This engine computes its result from the account.report.external.value objects that are linked to the expression.

        Two different formulas are possible:
        - sum: if the result must be the sum of all the external values in the period.
        - most_recent: it the result must be the value of the latest external value in the period, which can be a number or a text

        No subformula is allowed for this engine.
        """
        if current_groupby:
            raise UserError(self.env._("'external' engine does not support groupby."))

        # Date clause
        date_from, date_to = self._get_date_bounds_info(options, date_scope)
        external_value_domain = [('date', '<=', date_to)]
        if date_from:
            external_value_domain.append(('date', '>=', date_from))

        # Company clause
        external_value_domain.append(('company_id', 'in', self.get_report_company_ids(options)))

        # We have to execute two separate queries, one for text values and one for numeric values
        num_queries = []
        string_queries = []
        monetary_queries = []
        for formula, expressions in formulas_dict.items():
            groupby, orderby, limit = None, None, None
            if formula == 'most_recent':
                groupby, orderby, limit = SQL('date'), SQL('date DESC'), 1

            for expression in expressions:
                query = self.env['account.report.external.value'].with_context(date_to=date_to)._search(external_value_domain + [
                    ('target_report_expression_id', '=', expression.id),
                ], bypass_access=True)
                if expression.figure_type in self._get_accepted_figure_types():
                    query.order, query.limit = SQL('date DESC, id DESC'), 1
                    string_queries.append(query.select(
                        SQL("%s", expression.id),
                        query.table.text_value,
                    ))
                elif expression.figure_type == "monetary":
                    query.groupby, query.order, query.limit = groupby, orderby, limit
                    monetary_queries.append(query.select(
                        SQL("%s", expression.id),
                        SQL("COALESCE(SUM(COALESCE(CAST(value AS numeric) * %s, 0)), 0)", query.table.consolidation_rate),
                    ))
                else:
                    query.groupby, query.order, query.limit = groupby, orderby, limit
                    num_queries.append(query.select(
                        SQL("%s", expression.id),
                        SQL("SUM(COALESCE(value, 0))"),
                    ))

        # Convert to dict to have expression ids as keys
        query_results_dict = {}
        for query_list in (num_queries, string_queries, monetary_queries):
            if query_list:
                query_results = self.env.execute_query(SQL(' UNION ALL ').join(SQL("(%s)", query) for query in query_list))
                query_results_dict.update(dict(query_results))

        # Build result dict
        rslt = {}
        for formula, expressions in formulas_dict.items():
            for expression in expressions:
                expression_value = query_results_dict.get(expression.id)
                # If expression_value is None, we have no previous value for this expression (set default at 0.0)
                expression_value = expression_value or ('' if expression.figure_type in ('string', 'many2one') else 0.0)
                rslt[expression] = {'result': expression_value, 'has_sublines': False}

        return rslt

    def _report_engine_reference(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        formulas_dict = {'most_recent': sum(formulas_dict.values(), self.env['account.report.expression'])}
        return self._report_engine_external(options, date_scope, formulas_dict, current_groupby, warnings=warnings)

    def _compute_cumulative_translation_adjustment(self, options, date_scope):
        """
        Returns the values for the 'Cumulative Translation Adjustments' in BS and Trial Ledger reports.
        In case of consolidation of multiple companies having different main currency, the CTA value
        corresponds to the difference between the amounts converted at historical or average rates and
        current (closing rate at end date of the report) one. This only affect P&L and equity accounts
        since assets/liabilities are already using the current rate for this consolidation.

        :param options: The options for this report.
        :param date_scope: The date_scope under which to evaluate the query that fetches the amounts. Must be one
                           of account.report.expression's date_scope field's technical labels.
        :return: A dict containing the CTA debit, CTA credit and CTA balance.
        """
        if self.currency_translation != 'cta' or len({company_data['currency_id'] for company_data in options['companies']}) == 1:
            return {
                'balance': 0.0,
                'debit': 0.0,
                'credit': 0.0,
            }
        block_end_date = None
        if options.get('trial_balance_column_type') == 'initial_balance':
            block_end_date = options['date']['date_to']

        equity_income_expense_domain = Domain([
            ('account_type', 'in', [
                'equity', 'equity_unaffected', 'income', 'income_other',
                'expense_direct_cost', 'expense', 'expense_depreciation', 'expense_other'
            ]),
        ])

        combined_domain = equity_income_expense_domain & Domain(options.get('forced_domain', []))
        query = self._get_report_query(
            options | {'forced_domain': list(combined_domain)},
            date_scope,
            cta_date_to=block_end_date,
        )

        [(balance,)] = self.env.execute_query(query.select(
            SQL(
                "-COALESCE(SUM(%(cta)s), 0.0)",
                cta=query.table.cta_value),
            ),
        )
        return {
            'balance': balance,
            'debit': balance if balance > 0 else 0.0,
            'credit': -balance if balance < 0 else 0.0,
        }

    def _compute_cumulative_translation_adjustment_lines(self, options, date_scope):
        cta_line_name = self.env._("Cumulative Translation Adjustments")

        search_filter = options.get('filter_search_bar')
        if search_filter and search_filter.lower() not in cta_line_name.lower():
            return None

        cumulative_translation_adjustment_line = defaultdict(dict)

        for column_group_index, column_group_options in self._split_options_per_column_group(options).items():
            cta_values = self._compute_cumulative_translation_adjustment(column_group_options, date_scope)

            cumulative_translation_adjustment_line[column_group_index] = cta_values

        return AccountReportLineData(
            id=self._get_generic_line_id('account.report.line', None, markup='cumulative_translation_adjustment'),
            name=cta_line_name,
            level=1,
            columns=[
                self._build_column_data(
                    cumulative_translation_adjustment_line.get(column['column_group_index'], {}).get(
                        column['expression_label'],
                        0.0
                    ) if column['figure_type'] == 'monetary' else None,
                    column,
                    options=options
                )
                for column in options['columns']
            ],
            caret_options='cumulative_translation_adjustment',
        )

    def _generate_carryover_external_values(self, options):
        """ Generates the account.report.external.value objects corresponding to this report's carryover under the provided options.

        In case of multicompany setup, we need to split the carryover per company, for ease of audit, and so that the carryover isn't broken when
        a company leaves a tax unit.

        We first generate the carryover for the wholy-aggregated report, so that we can see what final result we want.
        Indeed due to force_between, if_above and if_below conditions, each carryover might be different from the sum of the individidual companies'
        carryover values. To handle this case, we generate each company's carryover values separately, then do a carryover adjustment on the
        main company (main for tax units, first one selected else) in order to bring their total to the result we computed for the whole unit.
        """
        self.ensure_one()

        if len(options['column_groups']) > 1:
            # The options must be forged in order to generate carryover values. Entering this conditions means this hasn't been done in the right way.
            raise UserError(_("Carryover can only be generated for a single column group."))

        # Get the expressions to evaluate from the report
        carryover_expressions = self.line_ids.expression_ids.filtered(lambda x: x.label.startswith('_carryover_'))
        expressions_to_evaluate = carryover_expressions._expand_aggregations()

        # Expression totals for all selected companies
        expression_totals_per_col_group = self._compute_expression_totals_for_each_column_group(expressions_to_evaluate, options)
        expression_totals = expression_totals_per_col_group[0]
        carryover_values = {expression: expression_totals[expression]['value'] for expression in carryover_expressions}

        if len(options['companies']) == 1:
            company = self.env['res.company'].browse(self.get_report_company_ids(options))
            self._create_carryover_for_company(options, company, {expr: result for expr, result in carryover_values.items()})
        else:
            multi_company_carryover_values_sum = defaultdict(lambda: 0)

            for company_opt in options['companies']:
                company = self.env['res.company'].browse(company_opt['id'])
                company_options = {**options, 'companies': [{'id': company.id, 'name': company.name}]}
                company_expressions_totals = self._compute_expression_totals_for_each_column_group(expressions_to_evaluate, company_options)
                company_carryover_values = {expression: company_expressions_totals[0][expression]['value'] for expression in carryover_expressions}
                self._create_carryover_for_company(options, company, company_carryover_values)

                for carryover_expr, carryover_val in company_carryover_values.items():
                    multi_company_carryover_values_sum[carryover_expr] += carryover_val

            # Adjust multicompany amounts on main company
            main_company = self._get_sender_company_for_export(options)
            for expr in carryover_expressions:
                difference = carryover_values[expr] - multi_company_carryover_values_sum[expr]
                self._create_carryover_for_company(options, main_company, {expr: difference}, label=_("Carryover adjustment for tax unit"))

    @api.model
    def _generate_default_external_values(self, date_from, date_to, is_tax_report=False):
        """ Generates the account.report.external.value objects for the given dates.
        If is_tax_report, the values are only created for tax reports, else for all other reports.
        """
        if date_from >= date_to:
            # This can happen when setting the lock date back in the past
            return

        options_dict = {}
        default_expr_by_report = defaultdict(list)
        tax_report = self.env.ref('account.generic_tax_report')
        company = self.env.company
        previous_options = {
            'date': {
                'date_from': date_from,
                'date_to': date_to,
            }
        }

        # Get all the default expressions from all reports
        default_expressions = self.env['account.report.expression'].search([('label', '=like', '_default_%')])
        # Options depend on the report, also we need to filter out tax report/other reports depending on is_tax_report
        # Hence we need to group the default expressions by report
        for expr in default_expressions:
            report = expr.report_line_id.report_id
            if is_tax_report == (tax_report in (report + report.root_report_id + report.section_main_report_ids.root_report_id)):
                if report not in options_dict:
                    options = report.with_context(allowed_company_ids=[company.id]).get_options(previous_options)
                    options_dict[report] = options

                if report._is_available_for(self.env['res.company'].browse(self.get_report_company_ids(options_dict[report]))):
                    default_expr_by_report[report].append(expr)

        external_values_create_vals = []
        for report, report_default_expressions in default_expr_by_report.items():
            options = options_dict[report]

            expressions_to_compute = {}
            for default_expression in report_default_expressions:
                # The default expression needs to have the same label as the target external expression, e.g. '_default_balance'
                target_label = default_expression.label[len('_default_'):]
                target_external_expression = default_expression.report_line_id.expression_ids.filtered(lambda x: x.label == target_label)
                # If the value has been created before/modified manually, we shouldn't create anything
                # and we won't recompute expression totals for them
                external_value = self.env['account.report.external.value'].search([
                    ('company_id', '=', company.id),
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                    ('target_report_expression_id', '=', target_external_expression.id),
                ])

                if not external_value:
                    expressions_to_compute[default_expression] = target_external_expression.id

            # Evaluate the expressions for the report to fetch the value of the default expression
            # These have to be computed for each fiscal position
            expression_totals_per_col_group = report.with_company(company)\
                ._compute_expression_totals_for_each_column_group(expressions_to_compute, options, include_default_vals=True)
            expression_totals = expression_totals_per_col_group[0]

            for expression, target_expression in expressions_to_compute.items():
                value = expression_totals[expression]['value']
                field_name = 'value' if isinstance(value, (int, float)) else 'text_value'
                external_values_create_vals.append({
                    'name': _("Manual value"),
                    field_name: expression_totals[expression]['value'],
                    'date': date_to,
                    'target_report_expression_id': target_expression,
                    'company_id': company.id,
                })

        self.env['account.report.external.value'].create(external_values_create_vals)

    @api.model
    def _get_sender_company_for_export(self, options):
        """ Return the sender company when generating an export file from this report.
            :return: self.env.company if not using a tax unit, else the main company of that unit
        """
        if options.get('tax_unit', 'company_only') != 'company_only':
            tax_unit = self.env['account.tax.unit'].browse(options['tax_unit'])
            return tax_unit.main_company_id

        report_companies = self.env['res.company'].browse(self.get_report_company_ids(options))
        options_main_company = report_companies[0]

        if options.get('tax_unit') is not None and options_main_company._get_branches_with_same_vat() == report_companies:
            # The line with the smallest number of parents in the VAT sub-hierarchy is assumed to be the root
            return report_companies.sorted(lambda x: len(x.parent_ids))[0]
        elif options_main_company._all_branches_selected():
            return options_main_company.root_id

        return options_main_company

    def _create_carryover_for_company(self, options, company, carryover_per_expression, label=None):
        date_from = options['date']['date_from']
        date_to = options['date']['date_to']

        external_values_create_vals = []
        for expression, carryover_value in carryover_per_expression.items():
            if not company.currency_id.is_zero(carryover_value):
                target_expression = expression._get_carryover_target_expression(options)
                external_values_create_vals.append({
                    'name': label or _("Carryover from %(date_from)s to %(date_to)s", date_from=format_date(self.env, date_from), date_to=format_date(self.env, date_to)),
                    'value': carryover_value,
                    'date': date_to,
                    'target_report_expression_id': target_expression.id,
                    'carryover_origin_expression_label': expression.label,
                    'carryover_origin_report_line_id': expression.report_line_id.id,
                    'company_id': company.id,
                })

        self.env['account.report.external.value'].create(external_values_create_vals)

    def get_default_report_filename(self, options, extension):
        """The default to be used for the file when downloading pdf,xlsx,..."""
        self.ensure_one()
        if title := options.get('report_title'):
            return title
        if 'sections_source_id' not in options:
            return _('report.%(file_extension)s', file_extension=extension)

        def _transform_period(period=""):
            if dates := re.findall(r'\d{2}/\d{2}/\d{4}', period):
                return f"{'_'.join(dates).replace('/', '')}"
            # We replace _-_ to handle periods with type 'quarter'
            return f"{period.replace(' ', '_').replace('_-_', '_').lower()}"

        def _get_company_name(companies):
            if companies and len(companies) == 1:
                return f"_{companies[0]['name'].replace(' ', '_').lower()}"
            return ""

        period = options.get('date', {}).get('string')
        sections_source_id = options['sections_source_id']
        if sections_source_id != self.id:
            sections_source = self.env['account.report'].browse(sections_source_id)
        else:
            sections_source = self

        return f"{sections_source.name.lower().replace(' ', '_')}_{_transform_period(period)}{_get_company_name(options['companies'])}.{extension}"

    def get_default_partner_report_filename(self, partner, options):
        self.ensure_one()
        custom_handler_model = self._get_custom_handler_model()
        if custom_handler_model and hasattr(self.env[custom_handler_model], '_get_partner_report_filename'):
            return self.env[custom_handler_model]._get_partner_report_filename(self, partner, options)

        default_file_name = self.get_default_report_filename(options, 'pdf')
        return f"{partner.name} - {default_file_name}"

    def execute_action(self, options, params=None):
        action_id = int(params.get('actionId'))
        action = self.env['ir.actions.actions'].sudo().browse([action_id])
        action_type = action.type
        action = self.env[action.type].sudo().browse([action_id])
        action_read = clean_action(action.read()[0], env=action.env)

        if action_type == 'ir.actions.client':
            # Check if we are opening another report. If so, generate options for it from the current options.
            if action.tag == 'account_report':
                target_report = self.env['account.report'].browse(ast.literal_eval(action_read['context'])['report_id'])
                new_options = target_report.get_options(previous_options=options)
                action_read.update({'params': {'options': new_options, 'ignore_session': True}})

        if params.get('id'):
            # Add the id of the calling object in the action's context
            if isinstance(params['id'], int):
                # id of the report line might directly be the id of the model we want.
                model_id = params['id']
            else:
                # It can also be a generic account.report id, as defined by _get_generic_line_id
                model_id = self._get_model_info_from_id(params['id'])[1]

            context = action_read.get('context') and literal_eval(action_read['context']) or {}
            context.setdefault('active_id', model_id)
            action_read['context'] = context

        return action_read

    def action_audit_cell(self, options, params):
        report_line = self.env['account.report.line'].browse(params['report_line_id'])
        expression_label = params['expression_label']
        expression = report_line.expression_ids.filtered(lambda x: x.label == expression_label)
        column_group_options = self._get_column_group_options(options, params['column_group_index'])

        # Audit of external values
        if expression.engine == 'external':
            date_from, date_to = self._get_date_bounds_info(column_group_options, expression.date_scope)
            external_values_domain = [('target_report_expression_id', '=', expression.id), ('date', '<=', date_to)]
            if date_from:
                external_values_domain.append(('date', '>=', date_from))

            if expression.formula == 'most_recent':
                query = self.env['account.report.external.value']._search(external_values_domain, bypass_access=True)
                rows = self.env.execute_query(SQL("""
                    SELECT ARRAY_AGG(id)
                    FROM %s
                    WHERE %s
                    GROUP BY date
                    ORDER BY date DESC
                    LIMIT 1
                """, query.from_clause, query.where_clause or SQL("TRUE")))
                if rows:
                    external_values_domain = [('id', 'in', rows[0][0])]

            return {
                'name': _("Manual values"),
                'type': 'ir.actions.act_window',
                'res_model': 'account.report.external.value',
                'view_mode': 'list',
                'views': [(False, 'list')],
                'domain': external_values_domain,
            }

        # Audit of move lines
        # If we're auditing a groupby line, we need to make sure to restrict the result of what we audit to the right group values
        column = next((col for col in report_line.report_id.column_ids if col.expression_label == expression_label), self.env['account.report.column'])
        if column.custom_audit_action_id:
            action_dict = column.custom_audit_action_id._get_action_dict()
        else:
            action_dict = {
                'name': _("Journal Items"),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move.line',
                'view_mode': 'list,pivot,graph,kanban',
                'context': {
                    'active_test': False,
                },
            }

        action = clean_action(action_dict, env=self.env)
        action['domain'] = self._get_audit_line_domain(column_group_options, expression, params)
        return action

    def action_view_all_variants(self, options, params):
        return {
            'name': _('All Report Variants'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.report',
            'view_mode': 'list',
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'active_test': False,
            },
            'domain': [('id', 'in', self._get_variants(options['variants_source_id'])._is_available_for(self.env['res.company'].browse(self.get_report_company_ids(options))).ids)],
        }

    def _get_audit_line_domain(self, column_group_options, expression, params):
        groupby_domain = Domain(self._get_audit_line_groupby_domain(params['calling_line_dict_id']))

        # Handle forced date scopes for cross-report expressions
        cross_report_match = CROSS_REPORT_REGEX.match(expression.subformula or '') if expression.engine == 'aggregation' else None
        force_date_scope = cross_report_match and cross_report_match['force_date_scope']

        # Aggregate all domains per date scope, then create the final domain.
        audit_or_domains_per_date_scope = defaultdict(list)
        for expression_to_audit in expression._expand_aggregations():
            expression_domain = self._get_expression_audit_aml_domain(expression_to_audit, column_group_options)

            if expression_domain is None:
                continue

            date_scope = expression.date_scope if force_date_scope else expression_to_audit.date_scope
            audit_or_domains_per_date_scope[date_scope].append(expression_domain)

        if audit_or_domains_per_date_scope:
            domain = Domain.OR(
                Domain.OR(audit_or_domains) & self._get_options_domain(column_group_options, date_scope)
                for date_scope, audit_or_domains in audit_or_domains_per_date_scope.items()
            )
        else:
            # Happens when no expression was provided (empty recordset), or if none of the expressions had a standard engine
            domain = self._get_options_domain(column_group_options, 'strict_range')
        domain &= groupby_domain

        return domain

    def _get_audit_line_groupby_domain(self, calling_line_dict_id):
        parsed_line_dict_id = self._parse_line_id(calling_line_dict_id)
        groupby_domain = []
        for markup, _model, grouping_key in parsed_line_dict_id:
            if isinstance(markup, dict) and 'groupby' in markup:
                groupby_field_name = markup['groupby']
                custom_handler_model = self._get_custom_handler_model()
                if custom_handler_model and (custom_groupby_data := self.env[custom_handler_model]._get_custom_groupby_map().get(groupby_field_name)):
                    groupby_domain += custom_groupby_data['domain_builder'](grouping_key)
                else:
                    groupby_domain.append((groupby_field_name, '=', grouping_key))

        return groupby_domain

    def _get_expression_audit_aml_domain(self, expression_to_audit, options):
        """ Returns the domain used to audit a single provided expression.

        'account_codes' engine's D and C formulas can't be handled by a domain: we make the choice to display
        everything for them (so, audit shows all the lines that are considered by the formula). To avoid confusion from the user
        when auditing such lines, a default group by account can be used in the list view.
        """
        if expression_to_audit.engine == 'account_codes':
            formula = expression_to_audit.formula.replace(' ', '')

            account_codes_domains = []
            for token in ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(formula.replace(' ', '')):
                if token:
                    match_dict = ACCOUNT_CODES_ENGINE_TERM_REGEX.match(token).groupdict()
                    tag_match = ACCOUNT_CODES_ENGINE_TAG_ID_PREFIX_REGEX.match(match_dict['prefix'])
                    account_codes_domain = []

                    if tag_match:
                        if tag_match['ref']:
                            tag_id = self.env['ir.model.data']._xmlid_to_res_id(tag_match['ref'])
                        else:
                            tag_id = int(tag_match['id'])

                        account_codes_domain.append(('account_id.tag_ids', 'in', [tag_id]))
                    else:
                        account_codes_domain.append(('account_id.code', '=like', f"{match_dict['prefix']}%"))

                    excluded_prefix_str = match_dict['excluded_prefixes']
                    if excluded_prefix_str:
                        for excluded_prefix in excluded_prefix_str.split(','):
                            # "'not like', prefix%" doesn't work
                            account_codes_domain += ['!', ('account_id.code', '=like', f"{excluded_prefix}%")]

                    account_codes_domains.append(account_codes_domain)

            return Domain.OR(account_codes_domains)

        if expression_to_audit.engine == 'tax_tags':
            tags = self.env['account.account.tag']._get_tax_tags(expression_to_audit.formula, expression_to_audit.report_line_id.report_id.country_id.id)
            return [('tax_tag_ids', 'in', tags.ids)]

        if expression_to_audit.engine == 'domain':
            return ast.literal_eval(expression_to_audit.formula)

        return None

    def open_journal_items(self, options, params):
        ''' Open the journal items view with the proper filters and groups '''
        markup, record_model, record_id = self._get_model_info_from_id(params.get('line_id'), include_markup=True)
        view_id = self.env.ref(params['view_ref']).id if params.get('view_ref') else None

        ctx = {
            'search_default_group_by_account': params.get('group_by_account', 1),
            'search_default_posted': 0 if options.get('all_entries') else 1,
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
            'search_default_journal_id': params.get('journal_id', False),
            'expand': 1,
        }

        recon_date = self._get_option_recon_date(options)
        if recon_date:
            ctx['search_default_open_on'] = recon_date
            ctx['search_default_unreconciled'] = True

        date_term = options['date'].get('date_from') and '_between' or '_before'
        ctx[f'search_default_date{date_term}'] = 1

        if options.get('selected_journal_groups'):
            ctx.update({
                'search_default_journal_group_id': [group['id'] for group in options.get('selected_journal_groups')],
            })

        journal_type = params.get('journal_type')
        group_journal_types = {group.get('journal_types') for group in options.get('selected_journal_groups', [])}
        if journal_type or options.get('selected_journal_groups') and group_journal_types:
            type_to_view_param = {
                'bank': {
                    'filter': 'search_default_bank',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_bank_cash').id
                },
                'cash': {
                    'filter': 'search_default_cash',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_bank_cash').id
                },
                'general': {
                    'filter': 'search_default_misc_filter',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_misc').id
                },
                'sale': {
                    'filter': 'search_default_sales',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_sales_purchases').id
                },
                'purchase': {
                    'filter': 'search_default_purchases',
                    'view_id': self.env.ref('account.view_move_line_tree_grouped_sales_purchases').id
                },
                'credit': {
                    'filter': 'search_default_credit',
                    'view_id': self.env.ref('account.view_move_line_tree').id
                },
            }
            if options.get('selected_journal_groups'):
                ctx_to_update = {}
                for journal_type in group_journal_types:
                    ctx_to_update[type_to_view_param[journal_type]['filter']] = 1
                ctx.update(ctx_to_update)
            else:
                ctx.update({
                    type_to_view_param[journal_type]['filter']: 1,
                })
            view_id = type_to_view_param[journal_type]['view_id']

        action_domain = [('display_type', 'not in', ('line_section', 'line_subsection', 'line_note'))]

        if record_id is None:
            # Default filters don't support the 'no set' value. For this case, we use a domain on the action instead
            model_fields_map = {
                'account.account': 'account_id',
                'res.partner': 'partner_id',
                'account.journal': 'journal_id',
            }
            model_field = model_fields_map.get(record_model)
            if model_field:
                action_domain += [(model_field, '=', False)]
        else:
            model_default_filters = {
                'account.account': 'search_default_account_id' if markup != 'parent_account' else 'search_default_account_with_children',
                'res.partner': 'search_default_partner_id',
                'account.journal': 'search_default_journal_id',
                'product.product': 'search_default_product_id',
                'product.category': 'search_default_product_category_id',
            }
            model_filter = model_default_filters.get(record_model)
            if model_filter:
                ctx.update({
                    'active_id': record_id,
                    model_filter: [record_id],
                })

        if options:
            for account_type in options.get('account_type', []):
                ctx.update({
                    f"search_default_{account_type['id']}": account_type['selected'] and 1 or 0,
                })

            if options.get('journals') and not ctx['search_default_journal_id']:
                selected_journals = [journal['id'] for journal in options['journals'] if journal.get('selected')]
                if len(selected_journals) == 1:
                    ctx['search_default_journal_id'] = selected_journals
                elif len(selected_journals) > 1 and len(selected_journals) < len(options['journals']):
                    ctx['search_default_journal_ids'] = True
                    ctx['journal_ids'] = selected_journals

        return {
            'name': self._get_action_name(params, record_model, record_id),
            'view_mode': 'list,pivot,graph,kanban',
            'res_model': 'account.move.line',
            'views': [(view_id, 'list')],
            'type': 'ir.actions.act_window',
            'domain': action_domain,
            'context': ctx,
        }

    def open_unallocated_items_journal_items(self, options, params):
        _record_model, record_id = self._get_model_info_from_id(params.get('line_id'))
        fiscal_year = self.env.company.compute_fiscalyear_dates(
            fields.Date.to_date(options.get('date').get('date_from'))
        )
        options_for_audit = {
            **options,
            'date': {
                **options['date'],
                'date_from': fields.Date.to_string(fiscal_year['date_from']),
                'date_to': fields.Date.to_string(fiscal_year['date_to']),
            },
        }

        action = self.open_journal_items(options=options_for_audit, params=params)
        action['domain'] += self._get_unallocated_earnings_lines_domain(action['context']['date_from'], record_id)
        action.get('context', {}).update({'search_default_date_between': 0})
        return action

    def _get_selected_journals_without_group(self, options, company):
        """
        Returns a recordset of the journals of the specified company that are not linked to a ledger (journal_group)
        """
        domain = [
            ('journal_group_id', '=', False),
            *self.env['account.journal']._check_company_domain(company)
        ]

        if options.get('journals'):
            domain.append(('id', 'in', [j['id'] for j in options['journals']]))

        rslt = self.env['account.journal'].search(domain)
        return rslt

    def open_unposted_moves(self, options, params=None):
        ''' Open the list of draft journal entries that might impact the reporting'''
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_journal_line")
        action = clean_action(action, env=self.env)
        action['domain'] = [('state', '=', 'draft'), ('date', '<=', options['date']['date_to'])]
        #overwrite the context to avoid default filtering on 'misc' journals
        action['context'] = {}
        return action

    def _get_generated_deferral_entries_domain(self, options):
        """Get the search domain for the generated deferral entries of the current period.

        :param options: the report's `options` dict containing `date_from`, `date_to` and `deferred_report_type`
        :return: a search domain that can be used to get the deferral entries
        """
        if options.get('deferred_report_type') == 'expense':
            account_types = ('expense', 'expense_depreciation', 'expense_direct_cost')
        else:
            account_types = ('income', 'income_other')
        date_to = fields.Date.from_string(options['date']['date_to'])
        date_to_next_reversal = fields.Date.to_string(date_to + datetime.timedelta(days=1))
        return [
            ('company_id', '=', self.env.company.id),
            # We exclude the reversal entries of the previous period that fall on the first day of this period
            ('date', '>', options['date']['date_from']),
            # We include the reversal entries of the current period that fall on the first day of the next period
            ('date', '<=', date_to_next_reversal),
            ('deferred_original_move_ids', '!=', False),
            ('line_ids.account_id.account_type', 'in', account_types),
            ('state', '!=', 'cancel'),
        ]

    def open_deferral_entries(self, options, params):
        domain = self._get_generated_deferral_entries_domain(options)
        deferral_line_ids = self.env['account.move'].search(domain).line_ids.ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Deferred Entries'),
            'res_model': 'account.move.line',
            'domain': [('id', 'in', deferral_line_ids)],
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'search_default_group_by_move': True,
                'expand': True,
            }
        }

    def action_modify_manual_value(self, line_id, options, column_group_index, new_value_str, target_expression_id, rounding, json_friendly_column_group_totals):
        """ Edit a manual value from the report, updating or creating the corresponding account.report.external.value object.

        :param options: The option dict the report is evaluated with.

        :param column_group_index: The string identifying the column group into which the change as manual value needs to be done.

        :param new_value_str: The new value to be set, as a string.

        :param rounding: The number of decimal digits to round with.

        :param json_friendly_column_group_totals: The expression totals by column group already computed for this report, in the format returned
                                                  by _get_json_friendly_column_group_totals. These will be used to reevaluate the report, recomputing
                                                  only the expressions depending on the newly-modified manual value, and keeping all the results
                                                  from the previous computations for the other ones.
        """
        self.ensure_one()

        target_column_group_options = self._get_column_group_options(options, column_group_index)

        if target_column_group_options.get('compute_budget'):
            expressions_to_recompute = self.env['account.report.expression'].browse(target_expression_id) \
                                       + self.line_ids.expression_ids.filtered(lambda x: x.engine == 'aggregation')
            self._action_modify_manual_budget_value(line_id, target_column_group_options, new_value_str, target_expression_id, rounding)
        else:
            expressions_to_recompute = self.line_ids.expression_ids.filtered(lambda x: x.engine in ('reference', 'external', 'aggregation'))
            self._action_modify_manual_external_value(target_column_group_options, new_value_str, target_expression_id, rounding)

        # We recompute values for each column group, not only the one we modified a value in; this is important in case some date_scope is used to
        # retrieve the manual value from a previous period.

        all_column_groups_expression_totals = self._convert_json_friendly_column_group_totals(
            json_friendly_column_group_totals,
            expressions_to_exclude=expressions_to_recompute,
        )

        recomputed_expression_totals = self._compute_expression_totals_for_each_column_group(
            expressions_to_recompute, options, forced_all_column_groups_expression_totals=all_column_groups_expression_totals)

        return {
            'lines': self._get_lines(options, all_column_groups_expression_totals=recomputed_expression_totals),
            'column_groups_totals': self._get_json_friendly_column_group_totals(recomputed_expression_totals),
        }

    def _convert_json_friendly_column_group_totals(self, json_friendly_column_group_totals, expressions_to_exclude=None, col_groups_to_exclude=None):
        """ json_friendly_column_group_totals contains ids instead of expressions (because it comes from js) ; this function is used
        to convert them back to records.
        """
        all_column_groups_expression_totals = {}
        for column_group_index, expression_totals in json_friendly_column_group_totals.items():
            column_group_index = int(column_group_index)
            if col_groups_to_exclude and column_group_index in col_groups_to_exclude:
                continue

            all_column_groups_expression_totals[column_group_index] = {}
            for expr_id, expr_totals in expression_totals.items():
                expression = self.env['account.report.expression'].browse(int(expr_id))  # Should already be in cache, so acceptable
                if not expressions_to_exclude or expression not in expressions_to_exclude:
                    all_column_groups_expression_totals[column_group_index][expression] = expr_totals

        return all_column_groups_expression_totals

    def _action_modify_manual_external_value(self, target_column_group_options, new_value_str, target_expression_id, rounding):
        """ Edit a manual value from the report, updating or creating the corresponding account.report.external.value object.

        :param target_column_group_options: The options dict of the column group where the modification happened.

        :param new_value_str: The new value to be set, as a string.

        :param target_expression_id:

        :param rounding: The number of decimal digits to round with.

        """
        if len(target_column_group_options['companies']) > 1:
            raise UserError(_("Editing a manual report line is not allowed when multiple companies are selected."))

        # Create the manual value
        target_expression = self.env['account.report.expression'].browse(target_expression_id)
        date_from, date_to = self._get_date_bounds_info(target_column_group_options, target_expression.date_scope)

        external_values_domain = [
            ('target_report_expression_id', '=', target_expression.id),
            ('company_id', '=', self.env.company.id),
        ]

        if target_expression.formula == 'most_recent' or target_expression.engine == 'reference':
            value_to_adjust = 0
            existing_value_to_modify = self.env['account.report.external.value'].search([
                *external_values_domain,
                ('date', '=', date_to),
            ])

            # There should be at most 1
            if len(existing_value_to_modify) > 1:
                raise UserError(_("Inconsistent data: more than one external value at the same date for a 'most_recent' external line."))
        else:
            existing_external_values = self.env['account.report.external.value'].search([
                *external_values_domain,
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ], order='date ASC')
            existing_value_to_modify = existing_external_values[-1] if existing_external_values and str(existing_external_values[-1].date) == date_to  else None
            value_to_adjust = sum(existing_external_values.filtered(lambda x: x != existing_value_to_modify).mapped('value'))

        if target_expression.figure_type in self._get_accepted_figure_types():
            values_to_set = {'text_value': new_value_str}

        else:
            try:
                float(new_value_str or '0')
            except ValueError:
                raise UserError(_("%s is not a numeric value", new_value_str))
            if target_expression.figure_type == 'boolean':
                rounding = 0
            values_to_set = {'value': float_round(float(new_value_str) - value_to_adjust, precision_digits=rounding)}

        if existing_value_to_modify:
            existing_value_to_modify.write(values_to_set)
            existing_value_to_modify.flush_recordset()
        else:
            self.env['account.report.external.value'].create({
                'name': _("Manual value"),
                **values_to_set,
                'date': date_to,
                'target_report_expression_id': target_expression.id,
                'company_id': self.env.company.id,
            })

    def _get_accepted_figure_types(self):
        return {'string', 'date', 'datetime', 'many2one'}

    def _action_modify_manual_budget_value(self, line_id, target_column_group_options, new_value_str, target_expression_id, rounding):
        target_expression = self.env['account.report.expression'].browse(target_expression_id)

        if not new_value_str and target_expression.figure_type != 'string':
            new_value_str = '0'

        try:
            value_to_set = float_round(float(new_value_str), precision_digits=rounding)
        except ValueError:
            raise UserError(_("%s is not a numeric value", new_value_str))

        model, account_id = self._get_model_info_from_id(line_id)
        if model != 'account.account':
            raise UserError(_("Budget items can only be edited from account lines."))

        # Depending on the expression's formula, the balance of the account could be multiplied by -1
        # within the report. We need to apply the same multiplier on the budget item we create.
        if target_expression.engine == 'domain' and target_expression.subformula.startswith('-'):
            value_to_set *= -1
        elif target_expression.engine == 'account_codes':
            account = self.env['account.account'].browse(account_id)

            # Search for the sign to apply to this account
            for token in ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(target_expression.formula.replace(' ', '')):
                if not token:
                    continue

                token_match = ACCOUNT_CODES_ENGINE_TERM_REGEX.match(token)
                multiplicator = -1 if token_match['sign'] == '-' else 1
                prefix = token_match['prefix']

                tag_match = ACCOUNT_CODES_ENGINE_TAG_ID_PREFIX_REGEX.match(prefix)
                if tag_match:
                    if tag_match['ref']:
                        tag = self.env.ref(tag_match['ref'])
                    else:
                        tag = self.env['account.account.tag'].browse(tag_match['id'])

                    account_matches = tag in account.tag_ids
                else:
                    account_matches = account.code.startswith(prefix)

                if account_matches:
                    value_to_set *= multiplicator
                    break

        self.env['account.report.budget'].browse(target_column_group_options['compute_budget'])._create_or_update_budget_items(
            value_to_set,
            account_id,
            rounding,
            target_column_group_options['date']['date_from'],
            target_column_group_options['date']['date_to'],
        )

    def action_display_inactive_sections(self, options):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': _("Enable Sections"),
            'view_mode': 'list,form',
            'res_model': 'account.report',
            'domain': [('section_main_report_ids', 'in', options['sections_source_id']), ('active', '=', False)],
            'views': [(False, 'list'), (False, 'form')],
            'context': {
                'list_view_ref': 'account_reports.account_report_add_sections_tree',
                'active_test': False,
            },
        }

    @api.model
    def sort_lines_from_client(self, minimal_lines, options):
        """
        Return indexes
        """
        def get_parent_id_func(line_element):
            return line_element[0]

        def get_id_func(line_element):
            return line_element[1]

        def get_no_format_func(line_element):
            return line_element[2]

        return self._sort_lines_common(minimal_lines, options, True, get_parent_id_func, get_id_func, get_no_format_func)

    @api.model
    def _sort_lines(self, lines, options):
        """
        Return the lines
        """
        def get_parent_id_func(line_element):
            return line_element.parent_id

        def get_id_func(line_element):
            return line_element.id

        def get_no_format_func(line_element):
            return line_element.columns[column_index].no_format

        column_index = None
        for index, col in enumerate(options['columns']):
            if options['order_column']['expression_label'] == col['expression_label']:
                column_index = index  # To know from which column to sort, used in merge_tree scope
                break

        if column_index is None:
            return lines

        return self._sort_lines_common(lines, options, False, get_parent_id_func, get_id_func, get_no_format_func)

    @api.model
    def _sort_lines_common(self, line_elements, options, result_as_index, get_parent_id_func, get_id_func, get_no_format_func):
        """ Sort report lines based on the 'order_column' key inside the options.
        The value of options['order_column'] is an integer, positive or negative, indicating on which column
        to sort and also if it must be an ascending sort (positive value) or a descending sort (negative value).
        Note that for this reason, its indexing is made starting at 1, not 0.
        If this key is missing or falsy, lines is returned directly.

        This method has some limitations:

            - The selected_column must have 'sortable' in its classes.
            - All lines are sorted except:

                - lines having the 'total' class
                - static lines (lines with model 'account.report.line')

            - This only works when each line has an unique id.
            - All lines inside the selected_column must have a 'no_format' value.

        Example::

            parent_line_1           balance=11
                child_line_1        balance=1
                child_line_2        balance=3
                child_line_3        balance=2
                child_line_4        balance=7
                child_line_5        balance=4
                child_line_6        (total line)
            parent_line_2           balance=10
                child_line_7        balance=5
                child_line_8        balance=6
                child_line_9        (total line)

        The resulting lines will be::

            parent_line_2           balance=10
                child_line_7        balance=5
                child_line_8        balance=6
                child_line_9        (total line)
            parent_line_1           balance=11
                child_line_1        balance=1
                child_line_3        balance=2
                child_line_2        balance=3
                child_line_5        balance=4
                child_line_4        balance=7
                child_line_6        (total line)

        :param line_elements:   The report lines or a minimal tuple containing data(web version).
        :param options: The report options.
        :param result_as_index: Whether the result return the line_elemens or the indexes.
        :param get_parent_id_func: Function to get the parent id from the line element
        :param get_id_func: Function to get the line id from the line element
        :param get_no_format_func: Function to get the no_format value from the sorted column of the line element
        :return:        Lines sorted by the selected column.
        """
        def needs_to_be_at_bottom(line_id):
            return self._get_markup(line_id) in ('total', 'load_more')

        def compare_values(a_line, b_line):
            type_seq = {
                type(None): 0,
                bool: 1,
                float: 2,
                int: 2,
                str: 3,
                datetime.date: 4,
                datetime.datetime: 5,
            }

            a_line_elem = line_elements[a_line] if result_as_index else a_line
            b_line_elem = line_elements[b_line] if result_as_index else b_line
            a_line_id = get_id_func(a_line_elem)
            b_line_id = get_id_func(b_line_elem)
            a_total = needs_to_be_at_bottom(a_line_id)
            b_total = needs_to_be_at_bottom(b_line_id)
            a_model = self._get_model_info_from_id(a_line_id)[0]
            b_model = self._get_model_info_from_id(b_line_id)[0]

            # static lines are not sorted
            if a_model == b_model == 'account.report.line':
                return 0

            if a_total:
                if b_total:  # a_total & b_total
                    return 0
                else:    # a_total & !b_total
                    return -1 if descending else 1
            if b_total:  # => !a_total & b_total
                return 1 if descending else -1

            a_val = get_no_format_func(a_line_elem)
            b_val = get_no_format_func(b_line_elem)
            type_a, type_b = type_seq[type(a_val)], type_seq[type(b_val)]

            if type_a == type_b:
                return 0 if a_val == b_val else 1 if a_val > b_val else -1
            else:
                return type_a - type_b

        def merge_tree(tree_elem, ls):
            nonlocal descending  # The direction of the sort is needed to compare total lines
            ls.append(tree_elem)

            elem = tree.get(get_id_func(line_elements[tree_elem]), []) if result_as_index else tree.get(get_id_func(tree_elem), [])

            for tree_subelem in sorted(elem, key=comp_key, reverse=descending):
                merge_tree(tree_subelem, ls)

        descending = options['order_column']['direction'] == 'DESC' # To keep total lines at the end, used in compare_values & merge_tree scopes

        comp_key = cmp_to_key(compare_values)
        sorted_list = []
        tree = {}
        non_total_parents = set()

        for index, line_element in enumerate(line_elements):
            line_parent = get_parent_id_func(line_element)
            tree.setdefault(line_parent, []).append(index if result_as_index else line_element)

            line_markup = self._get_markup(get_id_func(line_element))
            if line_markup != 'total':
                non_total_parents.add(line_parent)

        if None in tree:
            sorting_root = None
        else:
            # Expanding a groupby: all the lines should share the same hierachy. Each id starts with the parent's id, so the shortest id
            # has to be the root parent.
            sorting_root = min(non_total_parents, key=len)

        for line in sorted(tree[sorting_root], key=comp_key, reverse=descending):
            merge_tree(line, sorted_list)

        return sorted_list

    def _adjust_date_for_joined_comparison(self, options, period_date_from):
        comparison_filter = options.get('comparison', {}).get('filter')
        if comparison_filter == 'previous_period':
            last_comparison_date_dict = options['comparison'].get('periods', [{}])[-1]
            if last_comparison_date_dict:
                comparison_date_from = self._get_period_dates(options, fields.Date.to_date(last_comparison_date_dict['date_to']), last_comparison_date_dict['period_type'])[0]
                return min(period_date_from, comparison_date_from)
        return period_date_from

    def _adjust_domain_for_unjoined_comparison(self, options, dates_domain):
        comparison_filter = options.get('comparison', {}).get('filter')
        if comparison_filter and comparison_filter not in {'no_comparison', 'previous_period'}:
            unlinked_comparison_periods_domains_list = [
                Domain('date', '>=', period['date_from']) & Domain('date', '<=', period['date_to'])
                for period in options['comparison']['periods']
            ]
            unlinked_comparison_periods_domains_list.insert(0, dates_domain)
            dates_domain = Domain.OR(unlinked_comparison_periods_domains_list)

        return dates_domain

    def get_annotations_from_client(self, options, line_dict_ids_by_record):
        self.ensure_one()
        return self._get_annotations_common(options, line_dict_ids_by_record)

    def _get_annotations(self, options, lines):
        self.ensure_one()
        line_dict_ids_by_record = defaultdict(lambda: defaultdict(set))

        for line in lines:
            if line.chatter:
                line_dict_ids_by_record[line.chatter.model][str(line.chatter.id)].add(line.id)

        return self._get_annotations_common(options, line_dict_ids_by_record)

    def _get_annotations_common(self, options, line_dict_ids_by_record):
        """
        This method handles which annotations have to be displayed on the report.
        This decision is based on the different dates and mode of display of those dates in the report.

        param options: dict of options used to generate the report
        param line_dict_ids_by_record: dict of sets containing for each record (model, id) the set of line_dict ids linked to it
        return: dict of lists containing for each annotated line_id of the report the list of annotations linked to it
        """
        annotations_by_line = defaultdict(list)

        domain = Domain.OR([
            Domain('message_id.model', '=', model) & Domain('message_id.res_id', 'in', tuple(record_ids))
            for model, record_ids in line_dict_ids_by_record.items()
        ])
        if options.get('date'):
            period_date_from = self._get_period_dates(options, fields.Date.to_date(options['date']['date_to']), options['date']['period_type'])[0]
            period_date_from = self._adjust_date_for_joined_comparison(options, period_date_from)
            dates_domain = Domain('date', '>=', period_date_from) & Domain('date', '<=', options['date']['date_to'])
            domain &= self._adjust_domain_for_unjoined_comparison(options, dates_domain)

        order = 'create_date ASC' if options['export_mode'] else ''
        annotations = self.env['account.report.annotation'].search(domain, order=order)
        for annotation in annotations:
            message = annotation.message_id
            for line_id in line_dict_ids_by_record[message.model][str(message.res_id)]:
                if not options['export_mode']:
                    # When not exporting (so, coming from the client), we have no need for all the data of the annotation,
                    # as we rely on the chatter to fetch these informations when a line is selected.
                    annotations_by_line[line_id].append(message.id)
                else:
                    annotations_by_line[line_id].append({
                        'id': message.id,
                        'model': message.model,
                        'res_id': message.res_id,
                        'date': annotation.date,
                        'body': message.body,
                        'line_id': line_id,
                    })

        return annotations_by_line

    @api.model
    def _get_annotatable_models(self):
        return {'account.account', 'account.move', 'account.tax'}

    @api.model
    def _postprocess_chatter_for_annotations(self, lines):
        """ Add the chatter information on lines that can be annotated, so that it's then possible to open the right
        chatter for that line.
        """
        aml_id_to_report_lines_map = defaultdict(list)
        for line in lines:
            if line.unfoldable:
                continue

            model, record_id = self._get_model_info_from_id(line.id)
            if model == 'account.move.line' and record_id is not None:
                aml_id_to_report_lines_map[record_id].append(line)
            elif model in self._get_annotatable_models():
                line.chatter = AccountReportLineChatterData(model=model, id=record_id)

        aml_id_to_account_move_id = {
            line_data['id']: line_data['move_id']
            for line_data in self.env['account.move.line'].browse(aml_id_to_report_lines_map.keys()).read(['id', 'move_id'], load=False)
        }
        for aml_id, lines in aml_id_to_report_lines_map.items():
            for line in lines:
                line.chatter = AccountReportLineChatterData(model='account.move', id=aml_id_to_account_move_id[aml_id])

    def _get_last_comments_by_line(self, options, lines):
        annotations_by_line = self._get_annotations(options, lines)
        for line, annotations in annotations_by_line.items():
            last_annotation = annotations[0]['body'] if annotations else ''
            annotations_by_line[line] = markupsafe.Markup('<br/>').join(html2plaintext(last_annotation).split("\n"))
        return annotations_by_line

    def get_report_information(self, options):
        """
        return a dictionary of information that will be consumed by the AccountReport component.
        """
        self.ensure_one()
        self.env.flush_all()

        warnings = {}
        all_column_groups_expression_totals = self._compute_expression_totals_for_each_column_group(self.line_ids.expression_ids, options, warnings=warnings)

        # Convert all_column_groups_expression_totals to a json-friendly form (its keys are records)
        json_friendly_column_group_totals = self._get_json_friendly_column_group_totals(all_column_groups_expression_totals)

        lines = self._get_lines(options, all_column_groups_expression_totals=all_column_groups_expression_totals, warnings=warnings)

        return {
            'caret_options': self._get_caret_options(),
            'column_headers_render_data': self._get_column_headers_render_data(options),
            'column_groups_totals': json_friendly_column_group_totals,
            'context': self.env.context,
            'annotations': self._get_annotations(options, lines),
            'lines': lines,
            'warnings': warnings,
            'report': {
                'company_name': self.env.company.name,
                'company_country_code': self.env.company.country_code,
                'company_currency_symbol': self.env.company.currency_id.symbol,
                'name': self.name,
                'root_report_id': self.root_report_id,
            }
        }

    @api.readonly
    def get_report_information_readonly(self, options):
        """ Readonly version of get_report_information, to be called from RPC when options['readonly_query'] is True,
        to better spread the load on servers when possible.
        """
        return self.get_report_information(options)

    def _get_json_friendly_column_group_totals(self, all_column_groups_expression_totals):
        # Convert all_column_groups_expression_totals to a json-friendly form (its keys are records)
        json_friendly_column_group_totals = {}
        for column_group_index, expressions_totals in all_column_groups_expression_totals.items():
            json_friendly_column_group_totals[column_group_index] = {expression.id: totals for expression, totals in expressions_totals.items()}
        return json_friendly_column_group_totals

    def _is_available_for(self, companies):
        """ Called on report variants to know whether they are available in any of the provided companies or not.
        """
        main_company = companies[0]
        reports = self.filtered(lambda r: r.availability_condition == 'always')

        reports_by_country = self.filtered(lambda r: r.availability_condition == 'country')
        if reports_by_country:
            company_countries = main_company.account_fiscal_country_id

            reports_foreign_vat = reports_by_country.filtered('allow_foreign_vat')
            reports_no_foreign_vat = reports_by_country - reports_foreign_vat

            fp_countries = self.env['res.country']
            if reports_foreign_vat:
                foreign_vat_fpos = self.env['account.fiscal.position'].search([
                    ('foreign_vat', '!=', False),
                    ('company_id', '=', main_company.id),
                ])
                fp_countries |= foreign_vat_fpos.country_id

            reports += reports_by_country.filtered(lambda r: not r.country_id)
            reports += reports_no_foreign_vat.filtered(lambda r: r.country_id and r.country_id in company_countries)
            reports += reports_foreign_vat.filtered(lambda r: r.country_id and r.country_id in (company_countries | fp_countries))

        reports_by_coa = self.filtered(lambda r: r.availability_condition == 'coa')
        if reports_by_coa:
            # When restricting to 'coa', the report is only available if the main company has the same CoA as the report
            reports += reports_by_coa.filtered(lambda r: r.chart_template == main_company.chart_template)

        reports_by_consolidation = self.filtered(lambda r: r.availability_condition == 'consolidation')
        if reports_by_consolidation and len(companies) > 1:
            reports += reports_by_consolidation

        return reports

    def _get_column_headers_render_data(self, options):
        column_headers_render_data = {}

        # We only want to consider the columns that are visible in the current report and don't rely on self.column_ids
        # since custom reports could alter them (e.g. for multi-currency purposes)
        columns = [col for col in options['columns'] if col['column_group_index'] == next(index for index in range(len(options['column_groups'])))]

        # Compute the colspan of each header level, aka the number of single columns it contains at the base of the hierarchy
        level_colspan_list = column_headers_render_data['level_colspan'] = []
        for i in range(len(options['column_headers'])):
            nb_columns = max(len(columns), 1)
            colspan = nb_columns
            budget_col_number = 0

            for level_header in options['column_headers'][i + 1:]:
                # Separate non-budget and budget headers
                budget_base_count = sum(
                    [1 for header in level_header if header.get('forced_options', {}).get('budget_base')]
                )
                budget_amount_and_percentage_count = sum(
                    any(key in header.get('forced_options', {}) for key in ('compute_budget', 'budget_percentage'))
                    for header in level_header
                )
                non_budget_count = len(level_header) - budget_base_count - budget_amount_and_percentage_count

                # budget headers (amount and percentage) can only contain a single column each, regardless of the amount of columns in the report.
                # This implies that we first need to multiply for the 'regular' columns and then add the budget columns.
                colspan *= non_budget_count
                budget_col_number += (budget_base_count * nb_columns) + budget_amount_and_percentage_count

            level_colspan_list.append(colspan + budget_col_number)

        # Compute the number of times each header level will have to be repeated, and its colspan to properly handle horizontal groups/comparisons
        column_headers_render_data['level_repetitions'] = []
        for i in range(len(options['column_headers'])):
            colspan = 1
            for column_header in options['column_headers'][:i]:
                valid_headers_length = sum(
                    1 for item in column_header
                    if 'no_subheader_division' not in item.get('forced_options', {})
                )
                colspan *= valid_headers_length
            column_headers_render_data['level_repetitions'].append(colspan)

        # Custom reports have the possibility to define custom subheaders that will be displayed between the generic header and the column names.
        column_headers_render_data['custom_subheaders'] = options.get('custom_columns_subheaders', []) * len(options['column_groups'])

        return column_headers_render_data

    def _get_action_name(self, params, record_model=None, record_id=None):
        if not (record_model or record_id):
            record_model, record_id = self._get_model_info_from_id(params.get('line_id'))
        return params.get('name') or self.env[record_model].browse(record_id).display_name or ''

    def _format_lines_for_display(self, lines, options):
        """
        This method should be overridden in a report in order to apply specific formatting when printing
        the report lines.

        Used for example by the carryover functionnality in the generic tax report.
        :param lines: A list with the lines for this report.
        :param options: The options for this report.
        :return: The formatted list of lines
        """
        return lines

    def get_expanded_lines(self, options, line_dict_id, groupby, expand_function_name, horizontal_split_side, line_comparison_base_value, ignore_load_more=False, already_loaded_child_line_ids=None):
        self.env.flush_all()

        if not already_loaded_child_line_ids:
            already_loaded_child_line_ids = set()

        lines_to_skip_total_for = set()
        for already_loaded_line_id in already_loaded_child_line_ids:
            parsed_id = self._parse_line_id(already_loaded_line_id, markup_as_string=True)
            if parsed_id[-1][0] == 'total':
                # Rebuild parent id from total line's
                lines_to_skip_total_for.add(self._build_parent_line_id(parsed_id))

        lines = self._expand_unfoldable_line(
            expand_function_name,
            line_dict_id, groupby,
            options,
            horizontal_split_side,
            ignore_load_more=ignore_load_more,
            lines_to_skip_total_for=lines_to_skip_total_for,
        )
        lines = self._fully_unfold_lines_if_needed(lines, options, line_ids_to_skip=already_loaded_child_line_ids)

        if self.allow_account_audit_status_on_lines:
            lines = self._add_account_status_on_lines(lines, options)

        self._inject_account_names_for_consolidation(lines)

        if self.custom_handler_model_id:
            lines = self.env[self.custom_handler_model_name]._custom_line_postprocessor(self, options, lines)

        self._format_column_values(options, lines)
        self._update_line_comparison_data(options, lines, base_value=line_comparison_base_value)
        self._postprocess_chatter_for_annotations(lines)
        return lines

    @api.readonly
    def get_expanded_lines_readonly(self, options, line_dict_id, groupby, expand_function_name, horizontal_split_side, line_comparison_base_value, ignore_load_more=False, already_loaded_child_line_ids=None):
        """ Readonly version of get_expanded_lines_readonly, to be called from RPC when options['readonly_query'] is True,
        to better spread the load on servers when possible.
        """
        return self.get_expanded_lines(options, line_dict_id, groupby, expand_function_name, horizontal_split_side, line_comparison_base_value, ignore_load_more=ignore_load_more, already_loaded_child_line_ids=already_loaded_child_line_ids)

    def _expand_unfoldable_line(self, expand_function_name, line_dict_id, groupby, options, horizontal_split_side, unfold_all_batch_data=None, ignore_load_more=False, lines_to_skip_total_for=False):
        if not expand_function_name:
            raise UserError(_("Trying to expand a line without an expansion function."))

        expand_function = self._get_custom_report_function(expand_function_name, 'expand_unfoldable_line')
        expansion_result_lines = expand_function(
            line_dict_id,
            groupby,
            options,
            unfold_all_batch_data=unfold_all_batch_data,
            limit_to_load=None if ignore_load_more else self.load_more_limit,
        )

        if horizontal_split_side:
            for line in expansion_result_lines:
                line.horizontal_split_side = horizontal_split_side

        # Apply integer rounding to the result if needed.
        # The groupby expansion function is the only one guaranteed to call the expressions computation,
        # so the values computed for it will already have been rounded if integer rounding is enabled. No need to round them again.
        if expand_function_name != '_report_expand_unfoldable_line_with_groupby':
            self._apply_integer_rounding_to_dynamic_lines(options, expansion_result_lines)

        return self._add_totals_below_sections(expansion_result_lines, options, lines_to_skip_total_for=lines_to_skip_total_for)

    def _add_totals_below_sections(self, lines, options, lines_to_skip_total_for=False):
        """ Returns a new list, corresponding to lines with the required total lines added as sublines of the sections it contains.
        """
        if not self.env.company.totals_below_sections or options.get('ignore_totals_below_sections'):
            return lines

        if not lines_to_skip_total_for:
            lines_to_skip_total_for = set()

        # Gather the lines needing the totals
        lines_needing_total_below = set()
        for line_data in lines:
            line_markup = self._get_markup(line_data.id)

            if line_markup != 'total':
                # If we are on the first level of an expandable line, we arelady generate its total
                if line_data.unfoldable or (line_data.unfolded and line_data.expand_function):
                    lines_needing_total_below.add(line_data.id)

                # All lines that are parent of other lines need to receive a total
                line_parent_id = line_data.parent_id
                if line_parent_id:
                    lines_needing_total_below.add(line_parent_id)

        lines_needing_total_below -= lines_to_skip_total_for

        # Inject the totals
        if lines_needing_total_below:
            lines_with_totals_below = []
            totals_below_stack = []
            for line_data in lines:
                while totals_below_stack and not line_data.id.startswith(totals_below_stack[-1].parent_id + LINE_ID_HIERARCHY_DELIMITER):
                    lines_with_totals_below.append(totals_below_stack.pop())

                lines_with_totals_below.append(line_data)

                if line_data.id in lines_needing_total_below and any(col.no_format is not None for col in line_data.columns):
                    totals_below_stack.append(self._generate_total_below_section_line(line_data))

            while totals_below_stack:
                lines_with_totals_below.append(totals_below_stack.pop())

            return lines_with_totals_below

        return lines

    def _cleanup_empty_sections(self, lines):
        """ Resets the fold state for parents left without visible children, and removes their orphaned total lines.
        The total line removal only applies when called after _add_totals_below_sections.
        """
        # Collect parent IDs that still have at least one non-total child visible.
        # Total lines are generated from the parent itself and don't count as expandable children.
        parents_with_non_total_child = set()
        markups = {}
        for line in lines:
            markup = self._get_markup(line.id)
            markups[line.id] = markup
            if line.parent_id is not None and markup != 'total':
                parents_with_non_total_child.add(line.parent_id)

        result = []
        for line in lines:
            # Lines with an expand_function load their children on demand, so hide_if_zero doesn't affect them.
            if line.expand_function:
                result.append(line)
            elif markups[line.id] == 'total':
                # Keep report-level totals (no parent), and keep section totals only if
                # their parent still has non-total children.
                if line.parent_id is None or line.parent_id in parents_with_non_total_child:
                    result.append(line)
            elif line.id in parents_with_non_total_child:
                result.append(line)
            else:
                line.unfoldable = False
                line.unfolded = False
                result.append(line)

        return result

    def _report_expand_unfoldable_line_with_groupby(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        if groupby.split(',')[0].strip() == 'account_id':
            # When using account_groupes, we don't want to apply any limit (since the number of groups is unlikely to be high, and the
            # current implementation of account groups computes them base on lines, so after the load more limit has been applied)
            limit_to_load = None

        # The line we're expanding might be an inner groupby; we first need to find the report line generating it
        report_line_id = None
        for _markup, model, model_id in reversed(self._parse_line_id(line_dict_id)):
            if model == 'account.report.line':
                report_line_id = model_id
                break

        if report_line_id is None:
            raise UserError(_("Trying to expand a group for a line which was not generated by a report line: %s", line_dict_id))

        report_line = self.env['account.report.line'].browse(report_line_id)

        group_indent = 0
        line_id_list = self._parse_line_id(line_dict_id)

        # Parse groupby
        groupby_data = report_line._parse_groupby(options, groupby_to_expand=groupby)
        groupby_model = groupby_data['current_groupby_model']
        next_groupby = groupby_data['next_groupby']
        current_groupby = groupby_data['current_groupby']
        custom_groupby_map = groupby_data['custom_groupby_map']

        # If this line is a sub-groupby of groupby line (for example, when grouping by partner, id; the id line is a subgroup of partner),
        # we need to add the domain of the parent groupby criteria to the options
        sub_groupby_domain = []
        full_sub_groupby_key_elements = []
        parent_groupby_nber = 0
        for markup, model, value in line_id_list:
            if isinstance(markup, dict) and 'groupby' in markup:
                parent_groupby_nber += 1
                field_name = markup['groupby']
                if field_name in custom_groupby_map:
                    sub_groupby_domain += custom_groupby_map[field_name]['domain_builder'](value)
                else:
                    sub_groupby_domain.append((field_name, '=', value))
                full_sub_groupby_key_elements.append(f"{field_name}:{value}")

            if model == 'account.account' and markup == 'parent_account':
                group_indent += 1

        if sub_groupby_domain:
            forced_domain = options.get('forced_domain', []) + sub_groupby_domain
            options = {**options, 'forced_domain': forced_domain}

        # If the report transmitted custom_unfold_all_batch_data dictionary, use it
        full_sub_groupby_key = f"[{report_line.id}]{','.join(full_sub_groupby_key_elements)}=>{current_groupby}"

        cached_result = (unfold_all_batch_data or {}).get(full_sub_groupby_key)

        if cached_result is not None or options.get('test_unfold_all'):
            all_column_groups_expression_totals = cached_result
        else:
            all_column_groups_expression_totals = self._compute_expression_totals_for_each_column_group(
                report_line.expression_ids,
                options,
                groupby_to_expand=groupby,
            )

        # Put similar grouping keys from different totals/periods together, so that we don't display multiple
        # lines for the same grouping key

        figure_types_defaulting_to_0 = {'monetary', 'percentage', 'integer', 'float'}

        default_value_per_expr_label = {
            col_opt['expression_label']: 0 if col_opt['figure_type'] in figure_types_defaulting_to_0 else None
            for col_opt in options['columns']
        }

        # Gather default value for each expression, in case it has no value for a given grouping key
        default_value_per_expression = {}
        for expression in report_line.expression_ids:
            if expression.figure_type:
                default_value = 0 if expression.figure_type in figure_types_defaulting_to_0 else None
            else:
                default_value = default_value_per_expr_label.get(expression.label)

            default_value_per_expression[expression] = {'value': default_value}

        # Build each group's result
        all_group_results = []
        for column_group_index, expression_totals in all_column_groups_expression_totals.items():
            for expression in report_line.expression_ids:
                for grouping_key, result in expression_totals[expression]['value']:
                    all_group_results.append((grouping_key, result, column_group_index, expression))

        if pre_load_more_key_sort := custom_groupby_map.get(current_groupby, {}).get('pre_load_more_key_sort'):
            all_group_results.sort(key=pre_load_more_key_sort)

        all_group_totals_for_load_more = defaultdict(list)
        load_more_grouping_keys = set()
        aggregated_group_totals = defaultdict(lambda: defaultdict(default_value_per_expression.copy))
        for grouping_key, result, column_group_index, expression in all_group_results:
            if limit_to_load:
                all_group_total = all_group_totals_for_load_more[column_group_index, expression]

            sublines_info = all_column_groups_expression_totals[column_group_index][expression]['sublines_info']

            if limit_to_load and len(aggregated_group_totals) >= limit_to_load and grouping_key not in aggregated_group_totals:
                load_more_grouping_keys.add(grouping_key)
                all_group_total.append(result)
                continue

            aggregated_group_totals[grouping_key][column_group_index][expression] = {
                'value': result,
                'sublines_info': grouping_key in sublines_info,
            }

        load_more_line_count = len(load_more_grouping_keys)

        # Generate groupby lines
        group_lines_by_keys = {}
        columns_per_grouping_key = self._build_lines_columns(report_line, options, aggregated_group_totals, groupby_model=groupby_model)
        for grouping_key in aggregated_group_totals:

            # For this, we emulate a dict formatted like the result of _compute_expression_totals_for_each_column_group, so that we can call
            # _build_static_line_columns like on non-grouped lines
            line_id = self._get_generic_line_id(groupby_model, grouping_key, parent_line_id=line_dict_id, markup={'groupby': current_groupby})
            caret_option = None
            if not next_groupby:
                caret_builder = custom_groupby_map.get(current_groupby, {}).get('caret_builder', {})
                if caret_builder:
                    caret_option = caret_builder(grouping_key)
                else:
                    caret_option = groupby_model

            columns = columns_per_grouping_key[grouping_key]
            has_children = bool(next_groupby) and any(col.has_sublines for col in columns)

            group_line_data = AccountReportLineData(
                id=line_id,
                unfoldable=has_children,
                unfolded=(has_children and next_groupby and options['unfold_all']) or line_id in options['unfolded_lines'],
                groupby=next_groupby,
                columns=columns,
                level=report_line.hierarchy_level + 2 * (parent_groupby_nber + 1) + (group_indent - 1),
                parent_id=line_dict_id,
                expand_function='_report_expand_unfoldable_line_with_groupby' if next_groupby else None,
                caret_options=caret_option,
            )

            if self.custom_handler_model_id:
                self.env[self.custom_handler_model_name]._custom_groupby_line_completer(self, options, group_line_data, current_groupby)

            # Growth comparison column.
            if options.get('column_percent_comparison') == 'growth':
                compared_expression = report_line.expression_ids.filtered(lambda expr: expr.label == group_line_data.columns[0].expression_label)
                if options['comparison']['period_order'] == 'descending':
                    first_value, second_value = group_line_data.columns[0].no_format, group_line_data.columns[1].no_format
                else:
                    first_value, second_value = group_line_data.columns[1].no_format, group_line_data.columns[0].no_format

                group_line_data.column_percent_comparison_data = self._compute_column_percent_comparison_data(
                    options, first_value, second_value,
                    green_on_positive=compared_expression.green_on_positive, currency=group_line_data.columns[0].currency)
            # Manage budget comparison
            elif options.get('column_percent_comparison') == 'budget':
                self._set_budget_column_comparisons(options, group_line_data)

            group_lines_by_keys[grouping_key] = group_line_data

        draft_entries = {}  # move state used order to color the line if it's draft
        # Sort grouping keys in the right order and generate line names
        keys_and_names_in_sequence = {}  # Order of this dict will matter

        custom_groupby_name_builder = custom_groupby_map.get(current_groupby, {}).get('label_builder')
        if groupby_model and not custom_groupby_name_builder:
            records_to_sort = self.env[groupby_model].browse(key for key in group_lines_by_keys if key is not None)

            for record in records_to_sort.with_context(active_test=False).sorted():
                keys_and_names_in_sequence[record.id] = record.display_name

                if groupby_model == 'account.move.line':
                    draft_entries[record.id] = record.parent_state

                if groupby_model == 'account.move':
                    draft_entries[record.id] = record.state

            if None in group_lines_by_keys:
                keys_and_names_in_sequence[None] = _("Unknown")

        else:
            if custom_groupby_name_builder:
                keys_and_names_in_sequence = custom_groupby_name_builder(group_lines_by_keys.keys())  # Batch this when we have a label builder. This function also ensures the order of the name sequence
            else:
                for non_relational_key in sorted(group_lines_by_keys.keys(), key=lambda k: (k is None, isinstance(k, str), k)):
                    if non_relational_key is None:
                        keys_and_names_in_sequence[non_relational_key] = _("Undefined")
                    else:
                        groupby_field = self.env['account.move.line']._fields[groupby_data['current_groupby']]
                        if groupby_field.type == 'selection':
                            selection_options = dict(groupby_field._description_selection(self.env))
                            keys_and_names_in_sequence[non_relational_key] = selection_options.get(non_relational_key) or _("Undefined")
                        else:
                            keys_and_names_in_sequence[non_relational_key] = str(non_relational_key)

        # Build result: add a name to the groupby lines and handle totals below section for multi-level groupby
        group_lines = []
        for grouping_key, line_name in keys_and_names_in_sequence.items():
            group_line_data = group_lines_by_keys[grouping_key]
            group_line_data.name = line_name
            if draft_entries.get(grouping_key) == 'draft':
                group_line_data.is_draft = True
            group_lines.append(group_line_data)

        if options.get('hierarchy'):
            group_lines = self._create_hierarchy(group_lines, options)

        if load_more_line_count:
            group_lines.append(self._create_load_more_line(
                report_line,
                line_dict_id,
                options,
                all_group_totals_for_load_more,
                load_more_line_count,
                group_lines[-1].level,
                groupby,
                '_report_expand_unfoldable_line_with_groupby',
                custom_groupby_map.get(groupby, {}),
            ))

        return group_lines

    def _create_load_more_line(self, report_line, expanded_line_dict_id, options, all_group_totals_for_load_more, load_more_line_count, level, groupby, expand_function_name, custom_groupby_info):
        currency_expressions = self.line_ids.expression_ids.filtered(lambda x: x.label.startswith('_currency_'))
        foreign_currency_expression_labels = {cur_expr.label.replace('_currency_', '', 1) for cur_expr in currency_expressions}

        expressions_by_label = {expr.label: expr for expr in report_line.expression_ids}

        summary_columns = []
        for column_data in options['columns']:
            if column_data['figure_type'] == 'monetary' and column_data['expression_label'] not in foreign_currency_expression_labels and column_data['expression_label'] in expressions_by_label:

                values_to_sum = all_group_totals_for_load_more[column_data['column_group_index'], expressions_by_label[column_data['expression_label']]]
                if 'is_column_cumulative' in custom_groupby_info and custom_groupby_info['is_column_cumulative'](column_data['expression_label']):
                    values_to_sum = values_to_sum and [values_to_sum[-1]]

                if any(value is None for value in values_to_sum):
                    summary_columns.append(AccountReportColumnData())
                else:
                    summary_columns.append(self._build_column_data(sum(values_to_sum), column_data))
            else:
                summary_columns.append(AccountReportColumnData())

        return AccountReportLineData(
            id=self._get_generic_line_id(None, None, parent_line_id=expanded_line_dict_id, markup='load_more'),
            name=self.env._("%s more", load_more_line_count),
            level=level,
            parent_id=expanded_line_dict_id,
            expand_function=expand_function_name,
            columns=summary_columns,
            unfoldable=False,
            unfolded=False,
            groupby=groupby
        )

    def _format_value(self, options, value, figure_type, format_params=None):
        """ Formats a value for display in a report (not especially numerical). figure_type provides the type of formatting we want.
        """
        if value is None:
            return ''

        if figure_type == 'none':
            return value

        if figure_type == 'many2one' and value:
            res_model, res_id = value.split(':')
            if res_id.isdecimal():
                return self.env[res_model].browse(int(res_id)).display_name or ''

        if isinstance(value, str) or figure_type == 'string':
            return str(value)

        if format_params is None:
            format_params = AccountReportColumnFormatParamsData(currency_id=None, digits=None)

        formatLang_params = {
            'rounding_method': 'HALF-UP',
            'rounding_unit': options.get('rounding_unit'),
        }

        if figure_type == 'monetary':
            currency = self.env['res.currency'].browse(format_params.currency_id) if format_params.currency_id else self.env.company.currency_id
            if options.get('multi_currency'):
                formatLang_params['currency_obj'] = currency
            else:
                formatLang_params['digits'] = currency.decimal_places

        elif figure_type == 'integer':
            formatLang_params['digits'] = 0

        elif figure_type == 'boolean':
            return _("Yes") if bool(value) else _("No")

        elif figure_type in ('date', 'datetime'):
            return format_date(self.env, value)

        else:
            formatLang_params['digits'] = format_params.digits or 1

        if self._is_value_zero(value, figure_type, format_params):
            # Make sure -0.0 becomes 0.0
            value = abs(value)

        if self.env.context.get('no_format'):
            return value

        formatted_amount = formatLang(self.env, value, **formatLang_params)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        if figure_type == 'monetary' \
            and self.env.company.currency_id.compare_amounts(value, 0.0) < 0 \
            and self.env.company.account_reports_negative_format == 'parentheses':
            return f"({formatted_amount.replace('-', '')})"

        return formatted_amount

    @api.model
    def _is_value_zero(self, amount, figure_type, format_params):
        if amount is None:
            return True

        if figure_type == 'monetary':
            currency = self.env['res.currency'].browse(format_params.currency_id) if format_params.currency_id else self.env.company.currency_id
            return currency.is_zero(amount)
        elif figure_type in NUMBER_FIGURE_TYPES:
            return float_is_zero(amount, precision_digits=format_params.digits or 0)
        else:
            return False

    def export_file(self, options, file_generator, next_action=None):
        self.ensure_one()

        export_options = {**options, 'export_mode': 'file'}

        return {
            'type': 'ir_actions_account_report_download',
            'data': {
                'options': json.dumps(export_options),
                'file_generator': file_generator,
                'next_action': next_action,
            }
        }

    def _get_report_send_recipients(self, options):
        custom_handler_model = self._get_custom_handler_model()
        if custom_handler_model and hasattr(self.env[custom_handler_model], '_get_report_send_recipients'):
            return self.env[custom_handler_model]._get_report_send_recipients(options)
        return self.env['res.partner']

    def _get_display_journal_names_for_pdf(self, options):
        all_journals, _, names_company, names_journal_group, names_journal = self._get_journals_list_of_names(options)
        multiledger = False
        journals = False
        # If all journals and some groups are selected, display the group names
        # If all journals are selected but no group, display nothing (just the local journals of the company)
        selected_groups = [group for group in options.get('journal_groups') if group.get('selected')]
        if all_journals and selected_groups:
            multiledger = ", ".join([journal_group['name'] for journal_group in selected_groups])
        # If not all journals are selected
        if not all_journals and (len(names_journal) > 0 or len(names_journal_group) > 0):
            if len(names_journal) > 0:
                journals = ", ".join(names_company + names_journal)
            if len(names_journal_group) > 0:
                # Display ledger names
                multiledger = ", ".join(names_journal_group)
        return {
            'multiledger': multiledger,
            'journals': journals,
        }

    def _get_reports_to_print(self, options):
        # This method should be overridden to determine which reports or sections are included in the final PDF export.
        if options['sections']:
            return self.env['account.report'].browse([section['id'] for section in options['sections']])
        return self

    def _get_specific_paperformat_args(self, options):
        # This method should be overridden in a report in order to customize paper format arguments (e.g., margins, header spacing) passed to wkhtmltopdf for PDF generation.
        return {
            'data-report-margin-top': 10,
            'data-report-header-spacing': 10,
            'data-report-margin-bottom': 15,
        }

    def export_to_pdf(self, options):
        self.ensure_one()

        base_url = self.env['ir.config_parameter'].sudo().get_str('report.url') or self.env['ir.config_parameter'].sudo().get_str('web.base.url')
        rcontext = {
            'mode': 'print',
            'base_url': base_url,
            'company': self.env.company,
            'app_version': version,
        }

        print_options = self.get_options(previous_options={**options, 'export_mode': 'print'})
        reports_to_print = self._get_reports_to_print(print_options)

        reports_options = []
        for report in reports_to_print:
            reports_options.append(report.get_options(previous_options={**print_options, 'selected_section_id': report.id}))

        grouped_reports_by_format = groupby(
            zip(reports_to_print, reports_options),
            key=lambda report: len(report[1]['columns']) > 5 or report[1].get('horizontal_split') or report[1].get('force_landscape_printing')
        )

        footer = self._get_layout_footer(rcontext, options)

        action_report = self.env['ir.actions.report'].with_context(account_report_pdf_export=True)
        engine_name = self._get_pdf_engine_name(options)
        files_stream = []
        for is_landscape, reports_with_options in grouped_reports_by_format:
            bodies = []

            for report, report_options in reports_with_options:
                # Use custom handler's PDF export method if available
                custom_handler_model = report._get_custom_handler_model()
                handler = self.env[custom_handler_model] if (
                    custom_handler_model and hasattr(self.env[custom_handler_model], '_get_pdf_export_html')
                ) else report
                bodies.append(handler._get_pdf_export_html(
                    report_options,
                    report._filter_out_folded_children(report._get_lines(report_options)),
                    additional_context={'base_url': base_url}
                ))

            pdf_bytes = action_report._run_pdf_engine_without_processing(
                engine_name,
                bodies,
                landscape=is_landscape or self.env.context.get('force_landscape_printing'),
                footer=footer,
                specific_paperformat_args=self._get_specific_paperformat_args(options),
            )
            files_stream.append(io.BytesIO(pdf_bytes))

        if len(files_stream) > 1:
            result_stream = action_report._merge_pdfs(files_stream)
            result = result_stream.getvalue()
            # Close the different stream
            result_stream.close()
            for file_stream in files_stream:
                file_stream.close()
        else:
            result = files_stream[0].read()
            files_stream[0].close()

        return {
            'file_name': self.get_default_report_filename(options, 'pdf'),
            'file_content': result,
            'file_type': 'pdf',
        }

    def _get_layout_footer(self, rcontext, options=None):
        if self.env.context.get('exclude_page_footer'):
            return None
        else:
            options = options or {}
            custom_config = options.get('custom_display_config', {})
            layout_id = custom_config.get('pdf_export', {}).get('internal_layout') or "account_reports.internal_layout"
            footer_html = self.env['ir.actions.report']._render_template(layout_id, values=rcontext)
            footer_html = self.env['ir.actions.report']._render_template("web.minimal_layout", values=dict(rcontext, subst=True, body=markupsafe.Markup(footer_html.decode())))
            return footer_html.decode()

    def _get_pdf_export_html(self, options, lines, additional_context=None, template=None):
        report_info = self.get_report_information(options)

        custom_print_templates = options['custom_display_config'].get('pdf_export', {})
        template = custom_print_templates.get('pdf_export_main', 'account_reports.pdf_export_main')

        render_values = {
            'report': self,
            'report_title': options.get('report_title') or self.name,
            'options': options,
            'table_start': markupsafe.Markup('<tbody>'),
            'table_end': markupsafe.Markup('''
                </tbody></table></div>
                <div style="page-break-after: always"></div>
                <div class="d-flex align-items-start">
                <table class="o_table">
            '''),
            'column_headers_render_data': self._get_column_headers_render_data(options),
            'custom_templates': custom_print_templates,
        }
        if additional_context:
            render_values.update(additional_context)

        if options.get('order_column'):
            lines = self._sort_lines(lines, options)

        lines = self._format_lines_for_display(lines, options)

        render_values['lines'] = lines

        # Manage annotations.
        render_values['show_last_annotations'] = options.get('show_last_annotations')
        render_values['status_selection'] = dict(self.env['account.audit.account.status']._fields['status']._description_selection(self.env))
        if options.get('show_last_annotations'):
            last_annotations = self._get_last_comments_by_line(options, lines)
            for line in lines:
                line.update_values(last_comment=last_annotations.get(line.id))
        else:
            render_values['annotations'] = self._build_annotations_list_for_pdf_export(lines, report_info['annotations'])

        options['css_custom_class'] = options['custom_display_config'].get('css_custom_class', '')

        # Render.
        return self.env['ir.qweb']._render(template, render_values)

    def _build_annotations_list_for_pdf_export(self, lines, annotations_per_line_id):
        annotations_to_render = []
        record_to_number_map = {}
        for line in lines:
            line.annotations = []
            for annotation in annotations_per_line_id.get(line.id, []):
                if (number := record_to_number_map.get((annotation['model'], annotation['id']))):
                    line.annotations.append(str(number))
                    continue
                number = len(record_to_number_map) + 1
                record_to_number_map[annotation['model'], annotation['id']] = number
                line.annotations.append(str(number))
                annotations_to_render.append({
                    'number': str(number),
                    # wkhtmltopdf adds a <br> before tags such as p and div. This makes the first line of the body go down one line.
                    # we are losing some formatting here, but annotations shouldn't have complicated tags in them.
                    'body': markupsafe.Markup('<br/>').join(html2plaintext(annotation['body']).split("\n")),
                    'date': format_date(self.env, annotation['date']) if annotation['date'] else None,
                })
        return annotations_to_render

    def _filter_out_folded_children(self, lines):
        """ Returns a list containing all the lines of the provided list that need to be displayed when printing,
        hence removing the children whose parent is folded (especially useful to remove total lines).
        """
        rslt = []
        folded_lines = set()
        for line in lines:
            if line.unfoldable and not line.unfolded:
                folded_lines.add(line.id)

            if not line.parent_id or line.parent_id not in folded_lines:
                rslt.append(line)
        return rslt

    def export_to_xlsx(self, options, response=None):
        def add_worksheet_unique_name(workbook, sheet_name):
            existing_names = set(workbook.sheetnames.keys())
            count = 1
            max_length = 31
            new_sheet_name = sheet_name[:max_length]

            while new_sheet_name in existing_names:
                suffix = f" ({count})"
                truncated_name = sheet_name[:max_length - len(suffix)]
                new_sheet_name = f"{truncated_name}{suffix}"
                count += 1
            return workbook.add_worksheet(new_sheet_name)

        self.ensure_one()
        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {
            'in_memory': True,
            'strings_to_formulas': False,
        })

        print_options = self.get_options(previous_options={**options, 'export_mode': 'print'})
        if print_options['sections']:
            reports_to_print = self.env['account.report'].browse([section['id'] for section in print_options['sections']])
        else:
            reports_to_print = self

        reports_options = []
        for report in reports_to_print:
            report_options = report.get_options(previous_options={**print_options, 'selected_section_id': report.id})
            reports_options.append(report_options)
            # Use custom handler's XLSX export method if available
            custom_handler_model = report._get_custom_handler_model()
            if custom_handler_model and hasattr(self.env[custom_handler_model], '_inject_report_into_xlsx_sheet'):
                self.env[custom_handler_model]._inject_report_into_xlsx_sheet(report_options, workbook)
            else:
                report._inject_report_into_xlsx_sheet(report_options, workbook, add_worksheet_unique_name(workbook, report.name))

        self._add_options_xlsx_sheet(workbook, reports_options)

        workbook.close()
        output.seek(0)
        generated_file = output.read()
        output.close()

        return {
            'file_name': self.get_default_report_filename(options, 'xlsx'),
            'file_content': generated_file,
            'file_type': 'xlsx',
        }

    @api.model
    def _set_xlsx_cell_sizes(self, sheet, fonts, col, row, value, style, has_colspan):
        """ This small helper will resize the cells if needed, to allow to get a better output. """
        def get_string_width(font, string):
            return font.getlength(string) / 5

        # Get the correct font for the row style
        font_type = ('Bol' if style.bold else 'Reg') + ('Ita' if style.italic else '')
        report_font = fonts[font_type]

        # 8.43 is the default width of a column in Excel.
        import xlsxwriter  # noqa: PLC0415
        if parse_version(xlsxwriter.__version__) >= parse_version('3.0.6'):
            # cols_sizes was removed in 3.0.6 and colinfo was replaced by col_info
            # see https://github.com/jmcnamara/XlsxWriter/commit/860f4a2404549aca1eccf9bf8361df95dc574f44
            try:
                col_width = sheet.col_info[col][0]
            except KeyError:
                col_width = 8.43
        else:
            col_width = sheet.col_sizes.get(col, [8.43])[0]

        row_height = sheet.row_sizes.get(row, [8.43])[0]

        if value is None:
            value = ''
        else:
            try:  # noqa: SIM105
                # This is needed, otherwise we could compute width on very long number such as 12.0999999998
                # which wouldn't show well in the end result as the numbers are rounded.
                value = float_repr(float(value), self.env.company.currency_id.decimal_places)
            except (ValueError, OverflowError):
                pass

        # Start by computing the width of the cell if we are not using colspans.
        if not has_colspan:
            # Ensure to take indents into account when computing the width.
            formatted_value = f"{'  ' * style.indent}{value}"
            width = get_string_width(
                report_font,
                max(formatted_value.split('\n'), key=lambda line: get_string_width(report_font, line))
            )
            # We set the width if it is bigger than the current one, with a limit at 75 (max to avoid taking excessive space).
            if width > col_width:
                sheet.set_column(col, col, min(width + 4, 75))  # We need to add a little extra padding to ensure our columns are not clipping the text

    def _get_xlsx_export_fonts(self):
        """ Get the bold, italic and regular LATO font information so that we can use them for format purposes. """
        fonts = {}
        for font_type in ('Reg', 'Bol', 'RegIta', 'BolIta'):
            try:
                lato_path = f'web/static/fonts/lato/Lato-{font_type}-webfont.ttf'
                fonts[font_type] = ImageFont.truetype(file_path(lato_path), 12)
            except (OSError, FileNotFoundError):
                # This won't give great result, but it will work.
                fonts[font_type] = ImageFont.load_default()
        return fonts

    def _inject_report_into_xlsx_sheet(self, options, workbook, sheet):
        fonts = self._get_xlsx_export_fonts()

        def write_cell(sheet, x, y, value, style, colspan=1, rowspan=1, datetime=False):
            self._set_xlsx_cell_sizes(sheet, fonts, x, y, value, style, colspan > 1)
            if colspan == 1 and rowspan == 1:
                if datetime:
                    sheet.write_datetime(y, x, value, style)
                else:
                    sheet.write(y, x, value, style)
            else:
                sheet.merge_range(y, x, y + rowspan - 1, x + colspan - 1, value, style)

        default_format_props = {'font_name': 'Lato', 'font_size': 12, 'font_color': '#666666', 'num_format': '#,##0.00'}
        text_format_props = {'font_name': 'Lato', 'font_size': 12, 'font_color': '#666666'}
        date_format_props = {'font_name': 'Lato', 'font_size': 12, 'font_color': '#666666', 'align': 'left', 'num_format': 'yyyy-mm-dd'}
        title_format = workbook.add_format({'font_name': 'Lato', 'font_size': 12, 'bold': True, 'bottom': 2})
        annotation_format = workbook.add_format({**text_format_props, 'text_wrap': True})
        workbook_formats = {
            0: {
                'default': workbook.add_format({**default_format_props, 'bold': True, 'font_size': 13, 'bottom': 6}),
                'text': workbook.add_format({**text_format_props, 'bold': True, 'font_size': 13, 'bottom': 6}),
                'date': workbook.add_format({**date_format_props, 'bold': True, 'font_size': 13, 'bottom': 6}),
                'total': workbook.add_format({**default_format_props, 'bold': True, 'font_size': 13, 'bottom': 6}),
            },
            1: {
                'default': workbook.add_format({**default_format_props, 'bold': True, 'font_size': 13, 'bottom': 1}),
                'text': workbook.add_format({**text_format_props, 'bold': True, 'font_size': 13, 'bottom': 1}),
                'date': workbook.add_format({**date_format_props, 'bold': True, 'font_size': 13, 'bottom': 1}),
                'total': workbook.add_format({**default_format_props, 'bold': True, 'font_size': 13, 'bottom': 1}),
                'default_indent': workbook.add_format({**default_format_props, 'bold': True, 'font_size': 13, 'bottom': 1, 'indent': 1}),
                'date_indent': workbook.add_format({**date_format_props, 'bold': True, 'font_size': 13, 'bottom': 1, 'indent': 1}),
            },
            2: {
                'default': workbook.add_format({**default_format_props, 'bold': True}),
                'text': workbook.add_format({**text_format_props, 'bold': True}),
                'date': workbook.add_format({**date_format_props, 'bold': True}),
                'initial': workbook.add_format(default_format_props),
                'total': workbook.add_format({**default_format_props, 'bold': True}),
                'default_indent': workbook.add_format({**default_format_props, 'bold': True, 'indent': 2}),
                'date_indent': workbook.add_format({**date_format_props, 'bold': True, 'indent': 2}),
                'initial_indent': workbook.add_format({**default_format_props, 'indent': 2}),
                'total_indent': workbook.add_format({**default_format_props, 'bold': True, 'indent': 1}),
            },
            'default': {
                'default': workbook.add_format(default_format_props),
                'text': workbook.add_format(text_format_props),
                'date': workbook.add_format(date_format_props),
                'total': workbook.add_format(default_format_props),
                'default_indent': workbook.add_format({**default_format_props, 'indent': 2}),
                'date_indent': workbook.add_format({**date_format_props, 'indent': 2}),
                'total_indent': workbook.add_format({**default_format_props, 'indent': 2}),
            },
        }

        def get_format(content_type='default', level='default'):
            if isinstance(level, int) and level not in workbook_formats:
                workbook_formats[level] = {
                    **workbook_formats['default'],
                    'default_indent': workbook.add_format({**default_format_props, 'indent': level}),
                    'date_indent': workbook.add_format({**date_format_props, 'indent': level}),
                    'total_indent': workbook.add_format({**default_format_props, 'bold': True, 'indent': level - 1}),
                }

            level_formats = workbook_formats[level]
            if '_indent' in content_type and not level_formats.get(content_type):
                return level_formats.get('default_indent', level_formats.get(content_type.removesuffix('_indent'), level_formats['default']))
            return level_formats.get(content_type, level_formats['default'])

        print_mode_self = self.with_context(no_format=True)
        lines = self._filter_out_folded_children(print_mode_self._get_lines(options))
        annotations = self._get_annotations(options, lines)

        # For reports with lines generated for accounts, the account name and codes are shown in a single column.
        # To help user post-process the report if they need, we should in such a case split the account name and code in two columns.
        account_lines_split_names = {}
        for line in lines:
            line_model = self._get_model_info_from_id(line.id)[0]
            if line_model == 'account.account':
                # Reuse the _split_code_name to split the name and code in two values.
                account_lines_split_names[line.id] = self.env['account.account']._split_code_name(line.name)

        # Set the (Account) Name column width to 50.
        # If we have account lines and split the name and code in two columns, we will also set the code column.
        if len(account_lines_split_names) > 0:
            sheet.set_column(0, 0, 13)
            sheet.set_column(1, 1, 50)
        else:
            sheet.set_column(0, 0, 50)

        if not options.get('no_xlsx_currency_code_columns'):
            self._add_xlsx_currency_codes_columns(options, lines)

        # keep tracks of cells merged vertically
        merged_rowspan_cells = set()

        original_x_offset = 1 if len(account_lines_split_names) > 0 else 0

        y_offset = 0
        # 1 and not 0 to leave space for the line name. original_x_offset allows making place for the code column if needed.
        x_offset = original_x_offset + 1
        annotations_x_offset = 0
        annotations_header_written = False

        # Add headers.
        # For this, iterate in the same way as done in main_table_header template
        column_headers_render_data = self._get_column_headers_render_data(options)
        for header_level_index, header_level in enumerate(options['column_headers']):
            for header_to_render in header_level * column_headers_render_data['level_repetitions'][header_level_index]:
                colspan = header_to_render.get('colspan', column_headers_render_data['level_colspan'][header_level_index])
                colspan_with_horizontal_group = colspan + (1 if options['show_horizontal_group_total'] and header_level_index == 0 else 0)
                rowspan = len(options['column_headers']) - 1 if header_to_render.get('forced_options', {}).get('no_subheader_division') else 1

                while (x_offset, y_offset) in merged_rowspan_cells:
                    x_offset += 1

                write_cell(sheet, x_offset, y_offset, header_to_render.get('name', ''), title_format, colspan_with_horizontal_group, rowspan=rowspan)

                # tracks cells merged vertically
                if rowspan > 1:
                    for row in range(1, rowspan):
                        merged_rowspan_cells.update((x_offset + col, y_offset + row) for col in range(colspan_with_horizontal_group))

                x_offset += colspan
            if options.get('column_percent_comparison') in ('growth', 'analytic_coverage'):
                label = '%' if options['column_percent_comparison'] == 'analytic_coverage' or options['growth_display'] == 'percent' else self.env.company.currency_id.symbol
                write_cell(sheet, x_offset, y_offset, label, title_format)
                x_offset += 1

            if options['show_horizontal_group_total'] and header_level_index != 0:
                horizontal_group_name = next((group['name'] for group in options['available_horizontal_groups'] if group['id'] == options['selected_horizontal_group_id']), None)
                write_cell(sheet, x_offset, y_offset, horizontal_group_name, title_format)
                x_offset += 1
            if annotations:
                annotations_x_offset = x_offset
                write_cell(sheet, annotations_x_offset, y_offset, 'Annotations', title_format)
                annotations_header_written = True
                x_offset += 1
            y_offset += 1
            x_offset = original_x_offset + 1

        for subheader in column_headers_render_data['custom_subheaders']:
            colspan = subheader.get('colspan', 1)
            write_cell(sheet, x_offset, y_offset, subheader.get('name', ''), title_format, colspan)
            x_offset += colspan
        y_offset += 1
        x_offset = original_x_offset + 1

        if account_lines_split_names:
            # If we have a separate account code column, add a title for it
            write_cell(sheet, x_offset - 2, y_offset, _("Code"), title_format)
            write_cell(sheet, x_offset - 1, y_offset, _("Account Name"), title_format)
        sheet.set_column(x_offset, x_offset + len(options['columns']), 10)

        for column in options['columns']:
            colspan = column.get('colspan', 1)
            write_cell(sheet, x_offset, y_offset, column.get('name', ''), title_format, colspan)
            x_offset += colspan

        if options['show_horizontal_group_total']:
            write_cell(sheet, x_offset, y_offset, options['columns'][0].get('name', ''), title_format, colspan)

        if options.get('column_percent_comparison') in ('growth', 'analytic_coverage'):
            write_cell(sheet, x_offset, y_offset, '', title_format, colspan)
        if annotations and not annotations_header_written:
            # Fallback: if column_headers is empty the loop above never runs, so
            # annotations_x_offset was never set. x_offset already points to the
            # first free column after all data columns — the right spot for Annotations.
            annotations_x_offset = x_offset
            write_cell(sheet, annotations_x_offset, y_offset, 'Annotations', title_format)

        y_offset += 1

        if options.get('order_column'):
            lines = self._sort_lines(lines, options)

        # Disable bold styling for the max level.
        max_level = max(line.level or -1 for line in lines) if lines else -1
        if max_level in {0, 1, 2}:
            # Total lines are supposed to be a level above, so we don't touch them.
            for wb_format in (s for s in workbook_formats[max_level] if 'total' not in s):
                workbook_formats[max_level][wb_format].set_bold(False)

        lg = get_lang(self.env, self.env.user.lang)

        # Add lines.
        counter = 1
        for y, line in enumerate(lines):
            level = line.level
            if level == 0:
                y_offset += 1
            elif not level:
                level = 'default'

            line_id = self._parse_line_id(line.id)
            is_initial_line = line_id[-1][0] == 'initial' if line_id else False
            is_total_line = line_id[-1][0] == 'total' if line_id else False

            # Write the first column(s), with a specific style to manage the indentation.
            cell_type = 'text'
            cell_value = line.name or ''

            try:
                # the date is parsable to a xlsx compatible date
                cell_value = datetime.datetime.strptime(cell_value, lg.date_format)
                cell_type = 'date'
            except ValueError:
                # the date is not parsable thus is returned as text
                pass

            account_code_cell_format = get_format('text', level)

            if cell_type == 'date':
                cell_format = get_format('date_indent', level)
            elif is_initial_line:
                cell_format = get_format('initial_indent', level)
            elif is_total_line:
                cell_format = get_format('total_indent', level)
            else:
                cell_format = get_format('default_indent', level)

            x_offset = original_x_offset + 1
            if lines[y].id in account_lines_split_names:
                # Write the Account Code and Name columns.
                code, name = account_lines_split_names[lines[y].id]
                # Don't indent the account code and don't format is as a monetary value either.
                write_cell(sheet, 0, y + y_offset, code, account_code_cell_format)
                write_cell(sheet, 1, y + y_offset, name, cell_format)
            else:
                write_cell(sheet, original_x_offset, y + y_offset, cell_value, cell_format, datetime=cell_type == 'date')

                if line.parent_id and line.parent_id in account_lines_split_names:
                    write_cell(sheet, 1 + original_x_offset, y + y_offset, account_lines_split_names[line.parent_id][0], account_code_cell_format)
                elif account_lines_split_names:
                    write_cell(sheet, 1 + original_x_offset, y + y_offset, "", account_code_cell_format)

            # Write all the remaining cells.
            columns = line.columns
            if options.get('column_percent_comparison') and line.column_percent_comparison_data:
                columns += [line.column_percent_comparison_data]

            if options['show_horizontal_group_total']:
                columns += [line.horizontal_group_total_data or AccountReportColumnData(name=0)]
            company_currency = self.env.company.currency_id
            for x, column in enumerate(columns, start=x_offset):
                cell_value = column.name if column.name is not None else ''
                cell_type = 'text'
                if column.figure_type == 'monetary' and isinstance(cell_value, float):
                    currency = column.currency or company_currency
                    cell_value = currency.round(cell_value)
                if is_initial_line:
                    cell_format = get_format('initial', level)
                elif is_total_line:
                    cell_format = get_format('total', level)
                else:
                    cell_format = get_format('default', level)

                write_cell(sheet, x, y + y_offset, cell_value, cell_format, datetime=cell_type == 'date')

            # Write annotations.
            if annotations and (line_annotations := annotations.get(line.id)):
                line_annotation_text = []
                record_to_number_map = {}
                for line_annotation in line_annotations:
                    if (line_annotation['model'], line_annotation['id']) in record_to_number_map:
                        counter = record_to_number_map[line_annotation['model'], line_annotation['id']]
                    else:
                        counter = len(record_to_number_map) + 1
                        record_to_number_map[line_annotation['model'], line_annotation['id']] = counter

                    line_annotation_text.append(f"{counter} - {html_to_inner_content(line_annotation['body'])}")
                write_cell(sheet, annotations_x_offset, y + y_offset, "\n".join(line_annotation_text), annotation_format)

    def _add_xlsx_currency_codes_columns(self, options, lines):
        """ Adds a 'Currency Code' column for each column displaying amounts in foreign currencies. This is done because
        the raw number is displayed on the xlsx file, making it impossible to know the currency used.
        To have it displayed, the line must have an expression label starting with '_currency_' """
        required_currency_code_columns = {
            label.removeprefix('_currency_')
            for label in self.line_ids.expression_ids.mapped('label')
            if label.startswith('_currency_')
        }

        new_columns = []
        for col in options['columns']:
            new_columns.append(col)

            if col['expression_label'] in required_currency_code_columns:
                new_columns.append({
                    **col,
                    'name': _("Currency Code"),
                    'figure_type': 'string',
                    'expression_label': f"_xlsx_currency_code_{col['expression_label']}"
                })

        options['columns'] = new_columns

        # Add 'Currency Code' values to each line
        for line in lines:
            new_column_values = []

            for index, column in enumerate(line.columns):
                new_column_values.append(column)

                if column.expression_label in required_currency_code_columns:
                    currency = column.currency
                    currency_code = currency.name if currency else ''
                    new_column = self._build_column_data(currency_code, options['columns'][index + 1], options)
                    new_column.name = new_column.no_format
                    new_column_values.append(new_column)

            line.columns = new_column_values

    def _add_options_xlsx_sheet(self, workbook, options_list):
        """Adds a new sheet for xlsx report exports with a summary of all filters and options activated at the moment of the export."""
        filters_sheet = workbook.add_worksheet(_("Filters"))
        # Set first and second column widths.
        filters_sheet.set_column(0, 0, 20)
        filters_sheet.set_column(1, 1, 50)
        name_style = workbook.add_format({'font_name': 'Arial', 'bold': True, 'bottom': 2})
        y_offset = 0

        if len(options_list) == 1:
            self.env['account.report'].browse(options_list[0]['report_id'])._inject_report_options_into_xlsx_sheet(options_list[0], filters_sheet, y_offset)
            return

        # Find uncommon keys
        options_sets = list(map(set, options_list))
        common_keys = set.intersection(*options_sets)
        all_keys = set.union(*options_sets)
        uncommon_options_keys = all_keys - common_keys
        # Try to find the common filter values between all reports to avoid duplication.
        common_options_values = {}
        for key in common_keys:
            first_value = options_list[0][key]
            if all(options[key] == first_value for options in options_list[1:]):
                common_options_values[key] = first_value
            else:
                uncommon_options_keys.add(key)

        # Write common options to the sheet.
        filters_sheet.write(y_offset, 0, _("All"), name_style)
        y_offset += 1
        y_offset = self._inject_report_options_into_xlsx_sheet(common_options_values, filters_sheet, y_offset)

        for report_options in options_list:
            report = self.env['account.report'].browse(report_options['report_id'])

            filters_sheet.write(y_offset, 0, report.name, name_style)
            y_offset += 1
            new_offset = report._inject_report_options_into_xlsx_sheet(report_options, filters_sheet, y_offset, uncommon_options_keys)

            if y_offset == new_offset:
                y_offset -= 1
                # Clear the report name's cell since it didn't add any data to the xlsx.
                filters_sheet.write(y_offset, 0, " ")
            else:
                y_offset = new_offset

    def _inject_report_options_into_xlsx_sheet(self, options, sheet, y_offset, options_to_print=None):
        """
        Injects the report options into the filters sheet.

        :param options: Dictionary containing report options.
        :param sheet: XLSX sheet to inject options into.
        :param y_offset: Offset for the vertical position in the sheet.
        :param options_to_print: Optional list of names to print. If not provided, all printable options will be included.
        """
        def write_filter_lines(filter_title, filter_lines, y_offset):
            sheet.write(y_offset, 0, filter_title)
            for line in filter_lines:
                sheet.write(y_offset, 1, line)
                y_offset += 1
            return y_offset

        def should_print_option(option_key):
            """Check if the option should be printed based on options_to_print."""
            return not options_to_print or option_key in options_to_print

        # Company
        if should_print_option('companies'):
            companies = options['companies']
            title = _("Companies") if len(companies) > 1 else _("Company")
            lines = [company['name'] for company in companies]
            y_offset = write_filter_lines(title, lines, y_offset)

        # Journals
        if should_print_option('journals') and (journals := options.get('journals')):
            journal_titles = [journal.get('title') for journal in journals if journal.get('selected')]
            if journal_titles:
                y_offset = write_filter_lines(_("Journals"), journal_titles, y_offset)

        # Partners
        if should_print_option('selected_partner_ids') and (partner_names := options.get('selected_partner_ids')):
            y_offset = write_filter_lines(_("Partners"), partner_names, y_offset)

        # Partner categories
        if should_print_option('selected_partner_categories') and (partner_categories := options.get('selected_partner_categories')):
            y_offset = write_filter_lines(_("Partner Categories"), partner_categories, y_offset)

        # Line comparison
        if options.get('comparison', {}).get('filter') == 'report_line' and should_print_option('comparison'):
            y_offset = write_filter_lines(_("Comparison"), [options['comparison']['base_report_line']['name']], y_offset)

        # Horizontal groups
        if should_print_option('selected_horizontal_group_id') and (group_id := options.get('selected_horizontal_group_id')):
            for horizontal_group in options['available_horizontal_groups']:
                if horizontal_group['id'] == group_id:
                    filter_name = horizontal_group['name']
                    y_offset = write_filter_lines(_("Horizontal Group"), [filter_name], y_offset)
                    break

        # Currency
        if should_print_option('company_currency') and options.get('company_currency'):
            y_offset = write_filter_lines(_("Company Currency"), [options['company_currency']['currency_name']], y_offset)

        # Filters
        if should_print_option('aml_ir_filters'):
            if options.get('aml_ir_filters') and any(opt['selected'] for opt in options['aml_ir_filters']):
                filter_names = [opt['name'] for opt in options['aml_ir_filters'] if opt['selected']]
                y_offset = write_filter_lines(_("Filters"), filter_names, y_offset)

        # Extra options
        # Array of tuples for the extra options: (name, option_key, condition)
        extra_options = [
            (_("With Draft Entries"), 'all_entries', self.filter_show_draft),
            (_("Unreconciled Entries"), 'unreconciled', self.filter_unreconciled),
            (_("Including Analytic Simulations"), 'include_analytic_without_aml', True)
        ]
        filter_names = [
            name for name, option_key, condition in extra_options
            if (not options_to_print or option_key in options_to_print) and condition and options.get(option_key)
        ]
        if filter_names:
            y_offset = write_filter_lines(_("Options"), filter_names, y_offset)

        return y_offset

    def get_vat_for_export(self, options, raise_warning=True):
        """ Returns the VAT number to use when exporting this report with the provided
        options. If a single fiscal_position option is set, its VAT number will be
        used; else the current company's will be, raising an error if its empty.
        """
        self.ensure_one()

        if self.filter_multi_company == 'tax_units' and options['tax_unit'] != 'company_only':
            tax_unit = self.env['account.tax.unit'].browse(options['tax_unit'])
            return tax_unit.vat

        company = self._get_sender_company_for_export(options)

        if company.account_fiscal_country_id != self.country_id:
            foreign_vat_fpos = self.env['account.fiscal.position'].search([
                *self.env['account.fiscal.position']._check_company_domain(company),
                ('foreign_vat', '!=', False),
                ('country_id', '=', self.country_id.id)
            ], limit=1)
            if foreign_vat_fpos:
                return foreign_vat_fpos.foreign_vat

        if not company.has_vat and raise_warning:
            action = self.env.ref('base.action_res_company_form')
            raise RedirectWarning(_('No VAT number associated with your company. Please define one.'), action.id, _("Company Settings"))
        return company.vat

    @api.model
    def get_report_company_ids(self, options):
        """ Returns a list containing the ids of the companies to be used to
        render this report, following the provided options.
        """
        return [comp_data['id'] for comp_data in options['companies']]

    def _get_unallocated_earnings_lines_domain(self, fiscalyear_start, company_id=None):
        domain = [
            ('account_id.include_initial_balance', '=', False),
            ('date', '<', fiscalyear_start),
        ]
        if company_id:
            domain += [('company_id', '=', company_id)]
        return domain

    def _get_unallocated_earnings_lines(self, options, date_scope, auditable=False):
        def get_column_group_result(query_options, date_scope):
            query = self._get_report_query(query_options, date_scope, domain=self._get_unallocated_earnings_lines_domain(
                self.env[self.custom_handler_model_name]._get_fiscalyear_start_date(query_options)
            ))
            query.groupby = SQL('%s', query.table.company_id)
            return self.env.execute_query_dict(query.select(
                SQL('%s', query.table.company_id),
                SQL('COALESCE(SUM(%s), 0.0) AS balance', query.table.consolidation_balance),
                SQL('COALESCE(SUM(%s), 0.0) AS debit', query.table.consolidation_debit),
                SQL('COALESCE(SUM(%s), 0.0) AS credit', query.table.consolidation_credit),
            ))

        if not self.custom_handler_model_id:
            return []
        if options.get('filter_search_bar') and options.get('filter_search_bar') not in str(UNDISTR_LINE_NAME).lower():
            return []

        unallocated_earnings_lines = defaultdict(dict)
        company_to_line_id = dict()
        for column_group_index, column_group_options in self._split_options_per_column_group(options).items():
            # When groupby = id, the forced_domain is used to prevent displaying move lines that do not belong
            # to the period that is selected. In the unallocated earning lines, this is not needed.
            data = get_column_group_result(column_group_options | {
                'forced_domain': [domain for domain in column_group_options['forced_domain'] if domain != ('id', '=', False)],
            }, date_scope)

            for company_line in data:
                line_id = self._get_generic_line_id('res.company', company_line['company_id'], markup='undistributed_profits_losses')
                company_to_line_id[company_line['company_id']] = line_id
                unallocated_earnings_lines[column_group_index] |= {line_id: company_line}

        is_single_company = len(options['companies']) == 1
        report_currency = self.env.company.currency_id

        valid_company_lines = {
            company_id: line_id
            for company_id, line_id in company_to_line_id.items()
            if not all(
                report_currency.is_zero(col_group.get(line_id, {}).get('balance', 0.0))
                for col_group in unallocated_earnings_lines.values()
            )
        }

        rslt = []
        for company_id, line_id in valid_company_lines.items():
            columns = []
            for column in options['columns']:
                column = self._build_column_data(
                    unallocated_earnings_lines.get(column['column_group_index'], {}).get(line_id, {}).get(
                        column['expression_label'],
                        0.0 if column['figure_type'] == 'monetary' else None
                    ),
                    column,
                    options=options,
                )
                column.auditable = auditable
                columns.append(column)

            rslt.append(AccountReportLineData(
                id=line_id,
                name=(
                    str(UNDISTR_LINE_NAME) if is_single_company else
                    self.env._('%(line_name)s - %(company)s', line_name=UNDISTR_LINE_NAME, company=self.env['res.company'].browse(company_id).name)
                ),
                level=1,
                columns=columns,
                unfoldable=False,
                unfolded=False,
                caret_options='undistributed_profits_losses',
            ))

        return rslt

    def _get_partner_and_general_ledger_initial_balance_line(self, options, parent_line_id, eval_dict, account_currency=None, level_shift=0):
        """ Helper to generate dynamic 'initial balance' lines, used by general ledger and partner ledger.
        """
        line_columns = []
        for column in options['columns']:
            col_value = eval_dict[column['column_group_index']].get(column['expression_label'])
            col_expr_label = column['expression_label']

            if col_value is None or (col_expr_label == 'amount_currency' and not account_currency):
                line_columns.append(self._build_column_data(None, None))
            else:
                line_columns.append(self._build_column_data(
                    col_value,
                    column,
                    options=options,
                    currency=account_currency if col_expr_label == 'amount_currency' else None,
                ))

        # Display unfold & initial balance even when debit/credit column is hidden and the balance == 0
        if not any(isinstance(column.no_format, (int, float)) and column.expression_label != 'balance' for column in line_columns):
            return None

        return {
            'id': self._get_generic_line_id(None, None, parent_line_id=parent_line_id, markup='initial'),
            'name': _("Initial Balance"),
            'level': 3 + level_shift,
            'parent_id': parent_line_id,
            'columns': line_columns,
        }

    def _compute_column_percent_comparison_data(self, options, value1, value2, green_on_positive=True, currency=None):
        ''' Helper to get the additional columns due to the growth comparison feature. When only one comparison is
        requested, an additional column is there to show the percentage of growth based on the compared period.
        :param options:             The report options.
        :param value1:              The value in the current period.
        :param value2:              The value in the compared period.
        :param green_on_positive:   A flag customizing the value with a green color depending if the growth is positive.
        :param currency:            Currency used by the 'amount' display mode so multi-currency reports render correctly.
                                    Falls back to the company currency when not provided.
        :return:                    The new columns to add to line.columns.
        '''

        comparison_type = options['column_percent_comparison']
        is_monetary = comparison_type == 'growth' and options['growth_display'] == 'amount'
        if not isinstance(value1, (int, float)) or not isinstance(value2, (int, float)) or (float_is_zero(value2, precision_rounding=0.1) and not is_monetary):
            return AccountReportColumnData(name=_('n/a'), comparison_mode='muted')
        if comparison_type == 'growth':

            values_diff = value1 - value2
            if options['growth_display'] == 'amount':
                # Leave name unset so _format_column_values renders it against the current rounding_unit.
                currency = currency or self.env.company.currency_id
                comparison_mode = (
                    'muted' if float_is_zero(values_diff, precision_rounding=currency.rounding)
                    else ('red' if ((values_diff > 0) ^ green_on_positive) else 'green')
                )
                column_data = self._build_column_data(
                    values_diff,
                    {'figure_type': 'monetary', 'comparison_mode': comparison_mode},
                    options=options,
                    currency=currency,
                )
                column_data.green_on_positive = green_on_positive
                return column_data
            growth = round(values_diff / value2 * 100, 1)

            # In case the comparison is made on a negative figure, the color should be the other
            # way around. For example:
            #                       2018         2017           %
            # Product Sales      1000.00     -1000.00     -200.0%
            #
            # The percentage is negative, which is mathematically correct, but my sales increased
            # => it should be green, not red!
            if float_is_zero(growth, 1):
                return AccountReportColumnData(name='0.0%', comparison_mode='muted')
            else:
                return AccountReportColumnData(
                    name=f"{float_repr(growth, 1)}%",
                    comparison_mode='red' if ((values_diff > 0) ^ green_on_positive) else 'green',
                )

        elif comparison_type == 'budget':
            percentage_value = value1 / value2 * 100
            if float_is_zero(percentage_value, 1):
                # To avoid negative 0
                return AccountReportColumnData(name='0.0%', comparison_mode='green')

            comparison_value = float_compare(value1, value2, 1)
            return AccountReportColumnData(
                name=f"{float_repr(percentage_value, 1)}%",
                comparison_mode='green' if (comparison_value >= 0 and green_on_positive) or (comparison_value == -1 and not green_on_positive) else 'red',
            )

        elif comparison_type == 'analytic_coverage':
            coverage = round(value1 / value2 * 100, 1)
            if float_is_zero(coverage, precision_rounding=0.1):
                return AccountReportColumnData(name='0.0%', comparison_mode='muted')
            else:
                return AccountReportColumnData(
                    name=f"{coverage}%",
                    comparison_mode='green' if float_compare(coverage, 100, 1) == 0 else 'red',
                )

        elif comparison_type == 'report_line':
            percentage_value = round(value1 * 100 / value2, 1)
            comparison_value = float_compare(percentage_value, 100.0, precision_digits=1)

            return AccountReportColumnData(
                name=f"{float_repr(percentage_value, 1)}%",
                comparison_mode='' if comparison_value == 0 else ('green' if (comparison_value > 0) == green_on_positive else 'red'),
            )

    def _set_budget_column_comparisons(self, options, line):
        """
            Set the percentage values in the budget columns
        """
        for col_index, col in enumerate(line.columns):
            col_group_data = options['column_groups'][col.column_group_index]
            if 'budget_percentage' in col_group_data.get('forced_options', {}):
                budget_id = col_group_data['forced_options']['budget_percentage']
                date_key = col_group_data.get('forced_options', {}).get('date')
                if not date_key:
                    continue

                budget_base_col = None
                budget_amount_col = None
                for line_col in line.columns:
                    other_col_group_index = line_col.column_group_index
                    other_col_options = options['column_groups'][other_col_group_index]
                    if other_col_options.get('forced_options', {}).get('date') == date_key:
                        if other_col_options.get('forced_options', {}).get('budget_base') and line_col.figure_type == 'monetary' and line_col.expression_label == 'balance':
                            budget_base_col = line_col
                        elif other_col_options.get('forced_options', {}).get('compute_budget') == budget_id:
                            budget_amount_col = line_col
                if budget_base_col is None or budget_amount_col is None:
                    continue
                value = self._compute_column_percent_comparison_data(
                    options,
                    budget_base_col.no_format,
                    budget_amount_col.no_format,
                    green_on_positive=budget_base_col.green_on_positive,
                )

                comparison_column_data = budget_amount_col.as_dict()
                comparison_column_data['figure_type'] = 'string'
                comparison_column_data['comparison_mode'] = value.comparison_mode
                comparison_column = self._build_column_data(
                    value.name,
                    comparison_column_data,
                )
                line.columns[col_index] = comparison_column

    def _check_groupby_fields(self, groupby_fields_name: list[str] | str):
        """ Checks that each string in the groupby_fields_name list is a valid groupby value for an accounting report.
            So it must be:
            - a field from account.move.line which is (1) searchable and (2) for which _field_to_sql is implemented,
              this includes stored and related non-stored fields, or
            - a custom value allowed by the _get_custom_groupby_map function of the custom handler
        """
        self.ensure_one()
        if isinstance(groupby_fields_name, str | bool):
            groupby_fields_name = groupby_fields_name.split(',') if groupby_fields_name else []

        custom_handler_name = self._get_custom_handler_model()

        for field_name in (fname.strip() for fname in groupby_fields_name):
            groupby_field = self.env['account.move.line']._fields.get(field_name)
            if groupby_field:
                if not groupby_field._description_searchable:
                    raise UserError(self.env._("Field %s of account.move.line is not searchable and can therefore not be used in a groupby expression.", field_name))
                try:
                    aml = self.env['account.move.line']
                    aml._field_to_sql(aml._table, field_name, Query(aml))
                except ValueError:
                    raise UserError(self.env._("Field %s of account.move.line cannot be used in a groupby expression.", field_name)) from None
            elif custom_handler_name:
                if field_name not in self.env[custom_handler_name]._get_custom_groupby_map():
                    raise UserError(_("Field %s does not exist on account.move.line, and is not supported by this report's custom handler.", field_name))
            else:
                raise UserError(_("Field %s does not exist on account.move.line.", field_name))

    def _get_related_returns_domain(self, options):
        date_from, date_to = self._get_date_bounds_info(options, False)
        return Domain([
            ('type_id', 'in', self.return_type_ids.ids),
            ('date_from', '=', date_from),
            ('date_to', '=', date_to),
            ('company_id', 'in', self.get_report_company_ids(options)),
        ])

    def action_open_related_returns(self, options):
        self.ensure_one()
        returns_domain = self._get_related_returns_domain(options)
        related_returns = self.env['account.return'].search(returns_domain)

        if len(related_returns) == 1:
            return related_returns.action_open_account_return()

        return {
            **self.env.ref('account_reports.action_view_account_return')._get_action_dict(),
            'domain': returns_domain,
            'context': {'search_default_groupby_date_to': 1}
        }

    def action_open_returns(self, options):

        date_to = options['date']['date_to']
        date_from = options['date'].get('date_from') or fields.Date.to_string(fields.Date.from_string(date_to) - relativedelta(months=3))

        # If no return is found for the period and the return type, retry to generate them
        types_with_records = sum(
            (return_type for return_type, _return_count in self.env['account.return']._read_group(
                domain=Domain([
                    ('type_id', 'in', self.return_type_ids.ids),
                    ('date_to', '>=', date_from),
                    ('date_to', '<=', date_to),
                    ('company_id', 'in', self.env.companies.ids),
                ]),
                groupby=['type_id'],
                aggregates=['__count']
            )),
            self.env['account.return.type']
        )

        types_without_record = self.return_type_ids - types_with_records
        if types_without_record:
            root_companies = self.env['res.company'].sudo().search([
                ('account_opening_date', '!=', False),
                ('id', 'parent_of', self.env.companies.ids)
            ])
            self.env['account.return.type'].with_context(
                only_refresh_conditional_types=True
            )._generate_or_refresh_all_returns(root_companies)

        return self.env['account.return'].action_open_tax_return_view(
            additional_context={'filter_report_id': self.id, 'search_default_filter_report_id': True}
        )

    # ============ Accounts Coverage Debugging Tool - START ================
    @api.depends('country_id', 'chart_template', 'root_report_id')
    def _compute_is_account_coverage_report_available(self):
        for report in self:
            report.is_account_coverage_report_available = (
                (
                    report.availability_condition == 'country' and self.env.company.account_fiscal_country_id == report.country_id
                    or
                    report.availability_condition == 'coa' and self.env.company.chart_template == report.chart_template
                    or
                    report.availability_condition == 'always'
                )
                and
                report.root_report_id in (
                    self.env.ref('account_reports.profit_and_loss', raise_if_not_found=False),
                    self.env.ref('account_reports.balance_sheet', raise_if_not_found=False)
                )
            )

    def action_download_xlsx_accounts_coverage_report(self):
        """
        Generate an XLSX file that can be used to debug the
        report by issuing the following warnings if applicable:
        - an account exists in the Chart of Accounts but is not mentioned in any line of the report (red)
        - an account is reported in multiple lines of the report (orange)
        - an account is reported in a line of the report but does not exist in the Chart of Accounts (yellow)
        """
        self.ensure_one()
        if not self.is_account_coverage_report_available:
            raise UserError(_("The Accounts Coverage Report is not available for this report."))

        output = io.BytesIO()
        import xlsxwriter  # noqa: PLC0415
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Accounts coverage'))
        worksheet.set_column(0, 0, 20)
        worksheet.set_column(1, 1, 75)
        worksheet.set_column(2, 2, 80)
        worksheet.freeze_panes(1, 0)

        headers = [_("Account Code / Tag"), _("Error message"), _("Report lines mentioning the account code"), '#FFFFFF']
        lines = [headers] + self._generate_accounts_coverage_report_xlsx_lines()
        for i, line in enumerate(lines):
            worksheet.write_row(i, 0, line[:-1], workbook.add_format({'bg_color': line[-1]}))

        workbook.close()
        attachment_id = self.env['ir.attachment'].create({
            'name': f"{self.display_name} - {_('Accounts Coverage Report')}",
            'raw': output.getvalue(),
        })
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment_id.id}",
            "target": "download",
        }

    def _generate_accounts_coverage_report_xlsx_lines(self):
        """
        Generate the lines of the XLSX file that can be used to debug the
        report by issuing the following warnings if applicable:
        - an account exists in the Chart of Accounts but is not mentioned in any line of the report (red)
        - an account is reported in multiple lines of the report (orange)
        - an account is reported in a line of the report but does not exist in the Chart of Accounts (yellow)
        """
        def get_account_domain(prefix):
            # Helper function to get the right domain to find the account
            # This function verifies if we have to look for a tag or if we have
            # to look for an account code.
            if tag_matching := ACCOUNT_CODES_ENGINE_TAG_ID_PREFIX_REGEX.match(prefix):
                if tag_matching['ref']:
                    account_tag_id = self.env['ir.model.data']._xmlid_to_res_id(tag_matching['ref'])
                else:
                    account_tag_id = int(tag_matching['id'])
                return 'tag_ids', 'in', (account_tag_id,)
            else:
                return 'code', '=like', f'{prefix}%'

        self.ensure_one()

        AccountAccount = self.env['account.account'].with_context(active_test=False)
        all_reported_accounts = AccountAccount  # All accounts mentioned in the report (including those reported without using the account code)
        accounts_by_expressions = {}    # {expression_id: account.account objects}
        reported_account_codes = []     # [{'prefix': ..., 'balance': ..., 'exclude': ..., 'line': ...}, ...]
        non_existing_codes = defaultdict(lambda: self.env["account.report.line"])  # {non_existing_account_code: {lines_with_that_code,}}
        lines_per_non_linked_tag = defaultdict(lambda: self.env['account.report.line'])
        lines_using_bad_operator_per_tag = defaultdict(lambda: self.env['account.report.line'])
        candidate_duplicate_codes = defaultdict(lambda: self.env["account.report.line"])  # {candidate_duplicate_account_code: {lines_with_that_code,}}
        duplicate_codes = defaultdict(lambda: self.env["account.report.line"])  # {verified duplicate_account_code: {lines_with_that_code,}}
        duplicate_codes_same_line = defaultdict(lambda: self.env["account.report.line"])  # {duplicate_account_code: {line_with_that_code_multiple_times,}}
        common_account_domain = [
            *AccountAccount._check_company_domain(self.env.company),
        ]

        # tag_ids already linked to an account - avoid several search_count to know if the tag is used or not
        tag_ids_linked_to_account = set(AccountAccount.search([('tag_ids', '!=', False)]).tag_ids.ids)

        expressions = self.line_ids.expression_ids._expand_aggregations()
        for i, expr in enumerate(expressions):
            reported_accounts = AccountAccount
            if expr.engine == "domain":
                domain = literal_eval(expr.formula.strip())
                accounts_domain = []
                for j, operand in enumerate(domain):
                    if isinstance(operand, tuple):
                        operand = list(operand)
                        # Skip tuples that will not be used in the new domain to retrieve the reported accounts
                        if not operand[0].startswith('account_id.'):
                            if domain[j - 1] in ("&", "|", "!"):  # Remove the operator linked to the tuple if it exists
                                accounts_domain.pop()
                            continue
                        operand[0] = operand[0].replace('account_id.', '')
                        # Check that the code exists in the CoA
                        if operand[0] == 'code' and not AccountAccount.search_count([operand]):
                            non_existing_codes[operand[2]] |= expr.report_line_id
                        elif operand[0] == 'tag_ids':
                            tag_ids = operand[2]
                            if not isinstance(tag_ids, (list, tuple, set)):
                                tag_ids = [tag_ids]

                            if operand[1] in ('=', 'in'):
                                tag_ids_to_browse = [tag_id for tag_id in tag_ids if tag_id not in tag_ids_linked_to_account]
                                for tag in self.env['account.account.tag'].browse(tag_ids_to_browse):
                                    lines_per_non_linked_tag[f'{tag.name} ({tag.id})'] |= expr.report_line_id
                            else:
                                for tag in self.env['account.account.tag'].browse(tag_ids):
                                    lines_using_bad_operator_per_tag[f'{tag.name} ({tag.id}) - Operator: {operand[1]}'] |= expr.report_line_id

                    accounts_domain.append(operand)
                reported_accounts += AccountAccount.search(accounts_domain)
            elif expr.engine == "account_codes":
                account_codes = []
                for token in ACCOUNT_CODES_ENGINE_SPLIT_REGEX.split(expr.formula.replace(' ', '')):
                    if not token:
                        continue
                    token_match = ACCOUNT_CODES_ENGINE_TERM_REGEX.match(token)
                    if not token_match:
                        continue

                    parsed_token = token_match.groupdict()
                    account_codes.append({
                        'prefix': parsed_token['prefix'],
                        'balance': parsed_token['balance_character'],
                        'exclude': parsed_token['excluded_prefixes'].split(',') if parsed_token['excluded_prefixes'] else [],
                        'line': expr.report_line_id,
                    })

                for account_code in account_codes:
                    reported_account_codes.append(account_code)
                    exclude_domain_accounts = [get_account_domain(exclude_code) for exclude_code in account_code['exclude']]
                    reported_accounts += AccountAccount.search([
                        *common_account_domain,
                        get_account_domain(account_code['prefix']),
                        *[excl_domain for excl_tuple in exclude_domain_accounts for excl_domain in ("!", excl_tuple)],
                    ])

                    # Check that the code exists in the CoA or that the tag is linked to an account
                    prefixes_to_check = [account_code['prefix']] + account_code['exclude']
                    for prefix_to_check in prefixes_to_check:
                        account_domain = get_account_domain(prefix_to_check)
                        if not AccountAccount.search_count([
                            *common_account_domain,
                            account_domain,
                        ]):
                            # Identify if we're working with account codes or account tags
                            if account_domain[0] == 'code':
                                non_existing_codes[prefix_to_check] |= account_code['line']
                            elif account_domain[0] == 'tag_ids':
                                lines_per_non_linked_tag[prefix_to_check] |= account_code['line']

            all_reported_accounts |= reported_accounts
            accounts_by_expressions[expr.id] = reported_accounts

            # Check if an account is reported multiple times in the same line of the report
            if len(reported_accounts) != len(set(reported_accounts)):
                seen = set()
                for reported_account in reported_accounts:
                    if reported_account not in seen:
                        seen.add(reported_account)
                    else:
                        duplicate_codes_same_line[reported_account.code] |= expr.report_line_id

            # Check if the account is reported in multiple lines of the report
            for expr2 in expressions[:i + 1]:
                reported_accounts2 = accounts_by_expressions[expr2.id]
                for duplicate_account in (reported_accounts & reported_accounts2):
                    if len(expr.report_line_id | expr2.report_line_id) > 1 \
                       and expr.date_scope == expr2.date_scope \
                       and expr.subformula == expr2.subformula:
                        candidate_duplicate_codes[duplicate_account.code] |= expr.report_line_id | expr2.report_line_id

        # Check that the duplicates are not false positives because of the balance character
        for candidate_duplicate_code, candidate_duplicate_lines in candidate_duplicate_codes.items():
            if len(set(candidate_duplicate_lines.mapped('name'))) <= 1:
                continue
            seen_balance_chars = []
            for reported_account_code in reported_account_codes:
                if candidate_duplicate_code.startswith(reported_account_code['prefix']) and reported_account_code['balance']:
                    seen_balance_chars.append(reported_account_code['balance'])
            if not seen_balance_chars or seen_balance_chars.count("C") > 1 or seen_balance_chars.count("D") > 1:
                duplicate_codes[candidate_duplicate_code] |= candidate_duplicate_lines

        # Check that all codes in CoA are correctly reported
        if self.root_report_id == self.env.ref('account_reports.profit_and_loss'):
            accounts_in_coa = AccountAccount.search([
                *common_account_domain,
                ('account_type', 'in', ("income", "income_other", "expense", "expense_depreciation", "expense_direct_cost")),
                ('account_type', '!=', "off_balance"),
            ])
        else:  # Balance Sheet
            accounts_in_coa = AccountAccount.search([
                *common_account_domain,
                ('account_type', 'not in', ("off_balance", "income", "income_other", "expense", "expense_depreciation", "expense_direct_cost"))
            ])

        # Compute codes that exist in the CoA but are not reported in the report
        non_reported_codes = set((accounts_in_coa - all_reported_accounts).mapped('code'))

        # Create the lines that will be displayed in the xlsx
        all_reported_codes = sorted(set(all_reported_accounts.mapped("code")) | non_reported_codes | non_existing_codes.keys())
        errors_trie = self._get_accounts_coverage_report_errors_trie(all_reported_codes, non_reported_codes, duplicate_codes, duplicate_codes_same_line, non_existing_codes)
        errors_trie['children'].update(**self._get_account_tag_coverage_report_errors_trie(lines_per_non_linked_tag, lines_using_bad_operator_per_tag))  # Add tags that are not linked to an account

        errors_trie = self._regroup_accounts_coverage_report_errors_trie(errors_trie)
        return self._get_accounts_coverage_report_coverage_lines("", errors_trie)

    def _get_accounts_coverage_report_errors_trie(self, all_reported_codes, non_reported_codes, duplicate_codes, duplicate_codes_same_line, non_existing_codes):
        """
        Create the trie that will be used to regroup the same errors on the same subcodes.
        This trie will be in the form of:
        {
            "children": {
                "1": {
                    "children": {
                        "10": { ... },
                        "11": { ... },
                    },
                    "lines": {
                        "Line1",
                        "Line2",
                    },
                    "errors": {
                        "DUPLICATE"
                    }
                },
            "lines": {
                "",
            },
            "errors": {
                None    # Avoid that all codes are merged into the root with the code "" in case all of the errors are the same
            },
        }
        """
        errors_trie = {"children": {}, "lines": {}, "errors": {None}}
        for reported_code in all_reported_codes:
            current_trie = errors_trie
            lines = self.env["account.report.line"]
            errors = set()
            if reported_code in non_reported_codes:
                errors.add("NON_REPORTED")
            elif reported_code in duplicate_codes_same_line:
                lines |= duplicate_codes_same_line[reported_code]
                errors.add("DUPLICATE_SAME_LINE")
            elif reported_code in duplicate_codes:
                lines |= duplicate_codes[reported_code]
                errors.add("DUPLICATE")
            elif reported_code in non_existing_codes:
                lines |= non_existing_codes[reported_code]
                errors.add("NON_EXISTING")
            else:
                errors.add("NONE")

            for j in range(1, len(reported_code) + 1):
                current_trie = current_trie["children"].setdefault(reported_code[:j], {
                    "children": {},
                    "lines": lines,
                    "errors": errors
                })
        return errors_trie

    @api.model
    def _get_account_tag_coverage_report_errors_trie(self, lines_per_non_linked_tag, lines_per_bad_operator_tag):
        """ As we don't want to make a hierarchy for tags, we use a specific
            function to handle tags.
        """
        errors = {
            non_linked_tag: {
                'children': {},
                'lines': line,
                'errors': {'NON_LINKED'},
            }
            for non_linked_tag, line in lines_per_non_linked_tag.items()
        }
        errors.update({
            bad_operator_tag: {
                'children': {},
                'lines': line,
                'errors': {'BAD_OPERATOR'},
            }
            for bad_operator_tag, line in lines_per_bad_operator_tag.items()
        })
        return errors

    def _regroup_accounts_coverage_report_errors_trie(self, trie):
        """
        Regroup the codes that have the same error under the same common subcode/prefix.
        This is done in-place on the given trie.
        """
        if trie.get("children"):
            children_errors = set()
            children_lines = self.env["account.report.line"]
            if trie.get("errors"):  # Add own error
                children_errors |= set(trie.get("errors"))
            for child in trie["children"].values():
                regroup = self._regroup_accounts_coverage_report_errors_trie(child)
                children_lines |= regroup["lines"]
                children_errors |= set(regroup["errors"])
            if len(children_errors) == 1 and children_lines and children_lines == trie["lines"]:
                trie["children"] = {}
                trie["lines"] = children_lines
                trie["errors"] = children_errors
        return trie

    def _get_accounts_coverage_report_coverage_lines(self, subcode, trie, coverage_lines=None):
        """
        Create the coverage lines from the grouped trie. Each line has
        - the account code
        - the error message
        - the lines on which the account code is used
        - the color of the error message for the xlsx
        """
        # Dictionnary of the three possible errors, their message and the corresponding color for the xlsx file
        ERRORS = {
            "NON_REPORTED": {
                "msg": _("This account exists in the Chart of Accounts but is not mentioned in any line of the report"),
                "color": "#FF0000"
            },
            "DUPLICATE": {
                "msg": _("This account is reported in multiple lines of the report"),
                "color": "#FF8916"
            },
            "DUPLICATE_SAME_LINE": {
                "msg": _("This account is reported multiple times on the same line of the report"),
                "color": "#E6A91D"
            },
            "NON_EXISTING": {
                "msg": _("This account is reported in a line of the report but does not exist in the Chart of Accounts"),
                "color": "#FFBF00"
            },
            "NON_LINKED": {
                "msg": _("This tag is reported in a line of the report but is not linked to any account of the Chart of Accounts"),
                "color": "#FFBF00",
            },
            "BAD_OPERATOR": {
                "msg": _("The used operator is not supported for this expression."),
                "color": "#FFBF00",
            }
        }
        if coverage_lines is None:
            coverage_lines = []
        if trie.get("children"):
            for child in trie.get("children"):
                self._get_accounts_coverage_report_coverage_lines(child, trie["children"][child], coverage_lines)
        else:
            error = list(trie["errors"])[0] if trie["errors"] else False
            if error and error != "NONE":
                coverage_lines.append([
                    subcode,
                    ERRORS[error]["msg"],
                    " + ".join(trie["lines"].sorted().mapped("name")),
                    ERRORS[error]["color"]
                ])
        return coverage_lines

    # ============ Accounts Coverage Debugging Tool - END ================

    def _generate_file_data_with_error_check(self, options, content_generator, generator_params, errors):
        """ Checks for critical errors (i.e. errors that would cause the rendering to fail) in the generator values.
            If at least one error is critical, the 'account.report.file.download.error.wizard' wizard is opened
            before rendering the file, so they can be fixed.
            If there are only non-critical errors, the wizard is opened after the file has been generated,
            allowing the user to download it anyway.

            :param dict options: The report options.
            :param def content_generator: The function used to generate the exported content.
            :param dict generator_params: The parameters passed to the 'content_generator' method (List).
            :param list errors: A list of errors in the following format:
                [
                    {
                        'message': The error message to be displayed in the wizard (String),
                        'action_text': The text of the action button (String),
                        'action': Contains the action values (Dictionary),
                        'level': One of 'info', 'warning', 'danger'. (String).
                                 Only the 'danger' level represents a blocking error.
                    },
                    {...},
                ]
            :returns: The data that will be used by the file generator.
            :rtype: dict
        """
        if errors is None:
            errors = []
        self.ensure_one()

        content = content_generator(**generator_params)

        file_data = {
            'file_name': self.get_default_report_filename(options, generator_params['file_type']),
            'file_content': re.sub(r'\n\s*\n', '\n', content).encode(),
            'file_type': generator_params['file_type'],
        }

        if errors:
            raise AccountReportFileDownloadException(errors, file_data)

        return file_data

    def action_create_composite_report(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.report',
            'views': [[False, 'form']],
            'context': {
                'default_section_report_ids': self.ids,
            }
        }

    def show_error_branch_allowed(self, *args, **kwargs):
        raise UserError(_("Please select the main company and its branches in the company selector to proceed."))

    @api.model
    def get_available_variants(self):
        """ Return variants available for the selected companies for the command palette. """
        if not self.has_access('read'):
            return []
        root_reports = self.search([("root_report_id", "=", False), ("variant_report_ids", "!=", False)])
        all_variants = (root_reports | root_reports.variant_report_ids)
        available_variants = all_variants._is_available_for(self.env.companies)

        client_actions_sudo = self.env['ir.actions.client'].sudo().search([('tag', '=', 'account_report')])
        action_refs = [f'ir.actions.client,{a.id}' for a in client_actions_sudo]
        menus = self.env['ir.ui.menu'].search([('action', 'in', action_refs)])

        # Using menu items since they don't always match the name of the associated root report
        action_id_to_menu_name = {
            menu.action.id: menu.complete_name.replace('/', ' / ')
            for menu in menus
            if menu.action and menu.action._name == 'ir.actions.client'
        }

        report_data_map = {}
        for action in client_actions_sudo:
            ctx = action.context
            if isinstance(ctx, str):
                try:
                    ctx = ast.literal_eval(ctx)
                except (ValueError, SyntaxError):
                    continue

            if isinstance(ctx, dict):
                if report_id := ctx.get('report_id'):
                    report_data_map[report_id] = {
                        'action_id': action.id,
                        'menu_name': action_id_to_menu_name.get(action.id),
                    }

        return [
            {
                "id": variant.id,
                "display_name": variant.display_name,
                "root_report_id": variant.root_report_id.id,
                "root_report_path_name": report_data_map[variant.root_report_id.id].get('menu_name') or variant.root_report_id.name,
                "root_action_id": report_data_map[variant.root_report_id.id]['action_id'],
            }
            for variant in available_variants
            if variant.root_report_id and variant.root_report_id.id in report_data_map
        ]


class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    display_custom_groupby_warning = fields.Boolean(compute='_compute_display_custom_groupby_warning')

    @api.depends('groupby', 'user_groupby')
    def _compute_display_custom_groupby_warning(self):
        for line in self:
            line.display_custom_groupby_warning = line.get_external_id()[line.id] and line.user_groupby != line.groupby

    @api.constrains('groupby', 'user_groupby')
    def _validate_groupby(self):
        super()._validate_groupby()
        for report_line in self:
            report_line.report_id._check_groupby_fields(report_line.user_groupby)
            report_line.report_id._check_groupby_fields(report_line.groupby)

    def _parse_groupby(self, options=None, groupby_to_expand=None):
        """ Retrieves the information needed to handle the groupby feature on the current line.

        :param groupby_to_expand:    A coma-separated string containing, in order, all the fields that are used in the groupby we're expanding.
                                     None if we're not expanding anything.

        :return: A dictionary with 4 keys:
            'current_groupby':       The name of the value to be used to retrieve the results of the current groupby we're
                                     expanding, or None if nothing is being expanded. That value can be either a field of account.move.line, or
                                     a custom groupby value defined in this report's custom handler's _get_custom_groupby_map function.

            'next_groupby':          The subsequent groupings to be applied after current_groupby, as a string of coma-separated values (again,
                                     either field names from account.move.line or a custom groupby defined on the handler).
                                     If no subsequent grouping exists, next_groupby will be None.

            'current_groupby_model': The model name corresponding to current_groupby, or None if current_groupby is None.

            'custom_groupby_map';    The groupby map, used to handle custom groupby values, as returned by the _get_custom_groupby_map function
                                     of the custom handler (by default, it will be an empty dict)

        EXAMPLE:
            When computing a line with groupby=partner_id,account_id,id , without expanding it:
            - groupby_to_expand will be None
            - current_groupby will be None
            - next_groupby will be 'partner_id,account_id,id'
            - current_groupby_model will be None

            When expanding the first group level of the line:
            - groupby_to_expand will be: partner_id,account_id,id
            - current_groupby will be 'partner_id'
            - next_groupby will be 'account_id,id'
            - current_groupby_model will be 'res.partner'

            When expanding further:
            - groupby_to_expand will be: account_id,id ; corresponding to the next_groupby computed when expanding partner_id
            - current_groupby will be 'account_id'
            - next_groupby will be 'id'
            - current_groupby_model will be 'account.account'
        """
        self.ensure_one()

        if groupby_to_expand:
            groupby_to_expand = groupby_to_expand.replace(' ', '')
            split_groupby = groupby_to_expand.split(',')
            current_groupby = split_groupby[0]
            next_groupby = ','.join(split_groupby[1:]) if len(split_groupby) > 1 else None
        else:
            current_groupby = None
            groupby = self._get_groupby(options)
            next_groupby = groupby.replace(' ', '') if groupby else None

        custom_handler_name = self.report_id._get_custom_handler_model()
        custom_groupby_map = self.env[custom_handler_name]._get_custom_groupby_map() if custom_handler_name else {}
        if current_groupby in custom_groupby_map:
            groupby_model = custom_groupby_map[current_groupby]['model']
        elif current_groupby == 'id':
            groupby_model = 'account.move.line'
        elif current_groupby:
            f = self.env['account.move.line']._fields[current_groupby]
            groupby_model = f.comodel_name if f.relational else None
        else:
            groupby_model = None

        return {
            'current_groupby': current_groupby,
            'next_groupby': next_groupby,
            'current_groupby_model': groupby_model,
            'custom_groupby_map': custom_groupby_map,
        }

    def _get_groupby(self, options=None):
        self.ensure_one()

        if self.foldability == 'never_unfolded':
            return None

        if self.children_ids:
            return None

        if options and options['export_mode'] == 'file':
            return self.groupby or self.report_id.groupby

        groupby_lst = [groupby.strip() for groupby in (self.user_groupby or self.report_id.user_groupby or '').split(',')]
        if options and options['consolidation'] and 'account_id' in groupby_lst:
            index_account_id = groupby_lst.index('account_id')
            groupby_lst.insert(index_account_id, 'account_code')
            return ','.join(groupby_lst)

        return self.user_groupby or self.report_id.user_groupby

    def action_reset_custom_groupby(self):
        self.ensure_one()
        self.user_groupby = self.groupby


class AccountReportExpression(models.Model):
    _inherit = 'account.report.expression'

    def action_view_carryover_lines(self, options, column_group_index=None):
        if column_group_index:
            options = self.report_line_id.report_id._get_column_group_options(options, column_group_index)

        date_from, date_to = self.report_line_id.report_id._get_date_bounds_info(options, self.date_scope)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Carryover lines for: %s', self.report_line_name),
            'res_model': 'account.report.external.value',
            'views': [(False, 'list')],
            'domain': [
                ('target_report_expression_id', '=', self.id),
                ('date', '>=', date_from),
                ('date', '<=', date_to),
            ],
        }


class AccountReportExternalValue(models.Model):
    _inherit = 'account.report.external.value'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._check_lock_date_violation(set(self._build_vals_to_check_for_lock_date(records)))
        return records

    def write(self, vals):
        # We need to build vals_to_check before the super() call because of the 'target_report_expression_id' field :
        # if the user tries to modify this specific field, it'll potentially change the linked report id, and so he can
        # bypass the lock dates from the original report (if it was a tax report for example)
        vals_to_check = set(self._build_vals_to_check_for_lock_date(self))
        res = super().write(vals)
        # Then we add the modified records
        for lock_date_to_check in self._build_vals_to_check_for_lock_date(self):
            vals_to_check.add(lock_date_to_check)
        self._check_lock_date_violation(vals_to_check)
        return res

    @api.model
    def _build_vals_to_check_for_lock_date(self, records):
        """
        Generator method to build tuples out of records. The tuples will contain 3 values:
        - is tax, bool: is the external value linked to a tax report
        - date to check, date: the date we want to check the lock dates for
        - company, res.company: the company we want to check the lock dates for
        """
        generic_tax_report = self.env.ref('account.generic_tax_report')
        for external_value in records:
            report = external_value.target_report_expression_id.report_line_id.report_id
            yield (
                not self.env.context.get('ignore_tax_lock_date') and generic_tax_report in (report + report.root_report_id + report.section_main_report_ids.root_report_id),  # is tax
                external_value.date,  # date to check
                external_value.company_id,  # company
            )

    def _check_lock_date_violation(self, vals_to_check):
        """
        This method raises an error if the companies have lock dates after the date we want to create/write the values
        :param vals_to_check: a set of tuples like: `{(is_tax, date, company_id)}`
        """
        for is_tax, date, company_id in vals_to_check:
            violated_lock_dates = company_id._get_lock_date_violations(
                date,
                sale=False,
                purchase=False,
                tax=is_tax,
            )
            if violated_lock_dates:
                lock_date_names = [company_id._fields[lock_date[1]].get_description(self.env)['string'] for lock_date in violated_lock_dates]
                lock_dates = "\n- " + "\n- ".join(lock_date_names)
                raise ValidationError(_("You cannot update this value as it's locked by: %s", lock_dates))


class AccountReportHorizontalGroup(models.Model):
    _name = 'account.report.horizontal.group'
    _description = "Horizontal group for reports"

    name = fields.Char(string="Name", required=True, translate=True)
    rule_ids = fields.One2many(string="Rules", comodel_name='account.report.horizontal.group.rule', inverse_name='horizontal_group_id', required=True)
    report_ids = fields.Many2many(string="Reports", comodel_name='account.report')

    _name_uniq = models.Constraint(
        'unique (name)',
        "A horizontal group with the same name already exists.",
    )

    def _get_header_levels_data(self):
        return [
            (rule.field_name, rule._get_matching_records())
            for rule in self.rule_ids
        ]


class AccountReportHorizontalGroupRule(models.Model):
    _name = 'account.report.horizontal.group.rule'
    _description = "Horizontal group rule for reports"

    def _field_name_selection_values(self):
        return [
            (aml_field['name'], aml_field['string'])
            for aml_field in self.env['account.move.line'].fields_get().values()
            if aml_field['type'] in ('many2one', 'many2many')
        ]

    horizontal_group_id = fields.Many2one(string="Horizontal Group", comodel_name='account.report.horizontal.group', required=True, index=True)
    domain = fields.Char(string="Domain", required=True, default='[]')
    field_name = fields.Selection(string="Field", selection='_field_name_selection_values', required=True)
    res_model_name = fields.Char(string="Model", compute='_compute_res_model_name')

    @api.depends('field_name')
    def _compute_res_model_name(self):
        for record in self:
            if record.field_name:
                record.res_model_name = self.env['account.move.line']._fields[record.field_name].comodel_name
            else:
                record.res_model_name = None

    def _get_matching_records(self):
        self.ensure_one()
        model_name = self.env['account.move.line']._fields[self.field_name].comodel_name
        domain = ast.literal_eval(self.domain)
        return self.env[model_name].search(domain)


class AccountReportCustomHandler(models.AbstractModel):
    _name = 'account.report.custom.handler'
    _description = 'Account Report Custom Handler'

    # This abstract model allows case-by-case localized changes of behaviors of reports.
    # This is used for custom reports, for cases that cannot be supported by the standard engines.

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals, warnings=None):
        """ Generates lines dynamically for reports that require a custom processing which cannot be handled
        by regular report engines.
        :return:    A list of tuples [(sequence, line_dict), ...], where:
                    - sequence is the sequence to apply when rendering the line (can be mixed with static lines),
                    - line_dict is a dict containing all the line values.
        """
        return []

    def _caret_options_initializer(self):
        """ Returns the caret options dict to be used when rendering this report,
        in the same format as the one used in _caret_options_initializer_default (defined on 'account.report').
        If the result is empty, the engine will use the default caret options.
        """
        return self.env['account.report']._caret_options_initializer_default()

    def _custom_options_initializer(self, report, options, previous_options):
        """ To be overridden to add report-specific _init_options... code to the report. """
        pass

    def _custom_line_postprocessor(self, report, options, lines):
        """ Postprocesses the result of the report's _get_lines() before returning it. """
        return lines

    def _custom_groupby_line_completer(self, report, options, line_data, current_groupby):
        """ Postprocesses the dict generated by the group_by_line, to customize its content. """

    def _custom_unfold_all_batch_data_generator(self, report, options, lines_to_expand_by_function):
        """ When using the 'unfold all' option, some reports might end up recomputing the same query for
        each line to unfold, leading to very inefficient computation. This function allows batching this computation,
        and returns a dictionary where all results are cached, for use in expansion functions.
        """
        return None

    def _get_custom_groupby_map(self):
        """ Allows the use of custom values in the groupby field of account.report.line, to use them in custom engines. Those custom
        values can be anything, and need to be properly handled by the custom engine using them. This allows adding support for grouping on
        something else than just the fields of account.move.line, which is the default.

        :return:    A dict, in the form {groupby_name: {'model': model, 'domain_builder': domain_builder, ...}}, where:
                        - groupby_name is the custom value to use in groupby instead of one of aml's field names
                        - model: is a model name (a string), representing the model the value returned for this custom groupby targets.
                                 The model will be used to compute the display_name to show for each generated groupby line, in the UI.
                                 This value can be passed to None ; in such case, the raw value returned by the engine will be shown.
                        - domain_builder is a function to be called when expanding a groupby line generated by this custom groupby, to compute the
                                 domain to apply in order to restrict the computation to the content of this groupby line.
                                 This function must accept a single parameter, corresponding to the groupby value to compute the domain for.
                        - label_builder is a function to be called to compute a label for the groupby value, that will be shown as the line name
                                 in the UI. This ways, translatable labels and multi-values keys serialized to json can be fully supported.
                        - caret_builder is a function called with the grouping_key as parameter and that returns a custom caret identifier for this grouping key
                        - pre_load_more_key_sort is a function called with the grouping key as parameter, returning a sort key, used to order
                                 grouping keys before applying the load more limit. This can be used for example in case some engines involved in the
                                 grouping return an "initial balance" key, so that it can always be returned as the first result.
        """
        return {}

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        """ To be overridden to add report-specific warnings in the warnings dictionary.
        When a root report defines something in this function, its variants without any custom handler will also call the root report's
        _customize_warnings function. This can hence be used to share warnings between all variants.

        Should only be used when necessary, _dynamic_lines_generator is preferred.
        """


class AccountReportFileDownloadException(Exception):
    def __init__(self, errors, content=None):
        super().__init__()
        self.errors = errors
        self.content = content
