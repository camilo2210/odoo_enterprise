import json
import re
from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from markupsafe import Markup
from requests import RequestException

from odoo import _, api, fields, models, SUPERUSER_ID
from odoo.addons.l10n_in_reports.tools.gstr1_spreadsheet_generator import GSTR1SpreadsheetGenerator
from odoo.exceptions import UserError, AccessError, ValidationError, RedirectWarning
from odoo.fields import Domain
from odoo.tools import config, date_utils, formatLang, html_escape, SQL
from .irn_exception import IrnException

import logging

_logger = logging.getLogger(__name__)
TOLERANCE_AMOUNT = 1.0  # Default fallback tolerance amount for GSTR-2B matching if the system parameter is unset.

GSTR1_RETURN_TYPE = 'l10n_in_reports.in_gstr1_return_type'
GSTR2B_RETURN_TYPE = 'l10n_in_reports.in_gstr2b_return_type'
GSTR_IFF_RETURN_TYPE = 'l10n_in_reports.in_gstr_iff_return_type'
IFF_VALUE_LIMIT = 5000000
CMP08_RETURN_TYPE = 'l10n_in_reports.in_cmp08_return_type'
GSTR4_RETURN_TYPE = 'l10n_in_reports.in_gstr4_return_type'
GSTR_RETURN_TYPES = (GSTR1_RETURN_TYPE, GSTR2B_RETURN_TYPE, GSTR_IFF_RETURN_TYPE, CMP08_RETURN_TYPE, GSTR4_RETURN_TYPE)


class AccountReturnType(models.Model):
    _inherit = 'account.return.type'

    states_workflow = fields.Selection(
        selection_add=[('l10n_in_gstr1_status', 'India GSTR-1'), ('l10n_in_gstr2b_status', 'India GSTR-2B')],
        ondelete={'l10n_in_gstr1_status': 'cascade', 'l10n_in_gstr2b_status': 'cascade'},
    )

    def _try_create_returns_for_fiscal_year(self, main_company, tax_unit, allow_duplicates=False, bypass_period_check=False):
        """
        Override to check if GST e-Filing feature is enabled in configuration for Indian companies
        """
        self.ensure_one()

        gstr_return_types = self.env.ref('l10n_in_reports.in_gstr1_return_type') + self.env.ref('l10n_in_reports.in_gstr2b_return_type')
        if self not in gstr_return_types:
            return super()._try_create_returns_for_fiscal_year(main_company, tax_unit, allow_duplicates=allow_duplicates, bypass_period_check=bypass_period_check)

        if self in gstr_return_types:
            companies_with_no_gst_efiling = (
                self.env['account.return'].sudo()
                ._get_company_ids(main_company, tax_unit, self.report_id)
                .filtered(lambda c: not c.l10n_in_gst_efiling_feature)
            )
            if companies_with_no_gst_efiling:
                if self.env.context.get('manually_created'):
                    msg = self.env._(
                        "First enable GST e-Filing feature from configuration for company(s) %s.",
                        ", ".join(companies_with_no_gst_efiling.mapped('name'))
                    )
                    action = self.env.ref("account.action_account_config")
                    raise RedirectWarning(msg, action.id, self.env._('Go to configuration'))
                else:
                    return

        return super()._try_create_returns_for_fiscal_year(main_company, tax_unit, allow_duplicates=allow_duplicates, bypass_period_check=bypass_period_check)

    @api.model
    def _generate_all_returns(self, country_code, main_company, tax_unit=None, return_types=None):
        if country_code == 'IN' and main_company.l10n_in_gst_efiling_feature:
            if main_company.l10n_in_gst_registration_type == 'composition':
                composition_return_types = self.env.ref('l10n_in_reports.in_cmp08_return_type') + self.env.ref('l10n_in_reports.in_gstr4_return_type')
                for return_type in composition_return_types:
                    return_type._try_create_returns_for_fiscal_year(main_company, tax_unit)
            elif main_company.l10n_in_gst_registration_type == 'regular':
                regular_gst_return_types = self.env.ref('l10n_in_reports.in_gstr1_return_type') + self.env.ref('l10n_in_reports.in_gstr2b_return_type')
                for return_type in regular_gst_return_types:
                    return_type._try_create_returns_for_fiscal_year(main_company, tax_unit)
        super()._generate_all_returns(country_code, main_company, tax_unit=tax_unit, return_types=return_types)


class AccountReturn(models.Model):
    _inherit = 'account.return'

    # ===============================
    # GSTR-1
    # ===============================

    l10n_in_doc_summary_line_ids = fields.One2many('l10n_in.gstr.document.summary.line', 'return_period_id')
    l10n_in_gstr_reference = fields.Char(string="GSTR-1 Submit Reference")
    l10n_in_gstr1_status = fields.Selection(selection=[
        ('reviewed', 'Reviewed'),
        ('sending', 'Sent'),
        ('sending_error', 'Sending Error'),
        ('waiting_for_status', "Waiting for Status"),
        ('sent', 'Submitted'),
        ('error_in_invoice', 'Error in Invoice'),
        ('filed', 'Completed')
    ], readonly=True, tracking=True)
    l10n_in_gstr1_blocking_level = fields.Selection(
        selection=[('warning', 'Warning'), ('error', 'Error')],
        help="Blocks the current operation of the document depending on the error severity:\n"
        "  * Warning: there is an error that doesn't prevent the current Electronic Return filing operation to succeed.\n"
        "  * Error: there is an error that blocks the current Electronic Return filing operation.")
    l10n_in_month_year = fields.Char(compute="_compute_rtn_period_month_year", string="Return Period", store=True)

    # ===============================
    # GSTR-2B
    # ===============================

    l10n_in_gstr2b_status = fields.Selection(selection=[
        ('reviewed', 'Reviewed'),
        ('fetching', 'Fetching'),
        ('fetch', 'Fetched'),
        ('error_in_fetching', 'Error In Fetching'),
        ('matched', 'Matched'),
        ('partially_matched', 'Partially Matched'),
        ('completed', 'Completed')
    ], string="GSTR-2B Status", readonly=True, tracking=True)
    # if there is big data then it's give in multi-json
    l10n_in_gstr2b_json_ids = fields.Many2many('ir.attachment', 'account_return_gstr2b_json_rel', string='GSTR2B JSON from portal', bypass_search_access=True)
    l10n_in_gstr2b_blocking_level = fields.Selection(
        selection=[('warning', 'Warning'), ('error', 'Error')],
        help="Blocks the current operation of the document depending on the error severity:\n"
        "  * Warning: there is an error that doesn't prevent the current Electronic Return filing operation to succeed.\n"
        "  * Error: there is an error that blocks the current Electronic Return filing operation.")

    # ===============================
    # Bill using IRN
    # ===============================

    l10n_in_irn_status = fields.Selection(selection=[
        ('to_download', 'To Download'),
        ('to_process', 'To Process'),
        ('process_with_error', 'Process With Error')
    ], string="IRN Status", readonly=True, tracking=True)
    l10n_in_irn_json_attachment_ids = fields.Many2many('ir.attachment', 'irn_attachment_portal_account_return_json', string='JSON with list of IRNs', bypass_search_access=True)
    l10n_in_gstr_activate_einvoice_fetch = fields.Selection(related="company_id.l10n_in_gstr_activate_einvoice_fetch")
    l10n_in_fetch_vendor_edi_feature_enabled = fields.Boolean(related='company_id.l10n_in_fetch_vendor_edi_feature')
    l10n_in_irn_fetch_date = fields.Date(string="Last IRN Fetch Datetime")

    def _compute_show_submit_button(self):
        """
        For GSTR-1, submit button is visible when next state is 'sending' or next state is 'reviewed' and there is no unresolved check
        """
        super()._compute_show_submit_button()
        for record in self:
            if record.type_external_id in (GSTR1_RETURN_TYPE, GSTR_IFF_RETURN_TYPE):
                record.show_submit_button = (
                    record.next_state == 'sending'
                    or (
                        record.next_state == 'reviewed'
                        and not record.unresolved_check_count
                    )
                )

    def _compute_visible_states(self):
        """
        Extend base state computation to apply custom visibility and alert styling
        for Indian GST return types (GSTR1 and GSTR2B).

        General Rule:
        - All states up to the current status remain active.
        - Each visible state gets an `alert_type`:
            * success   → completed successfully
            * warning   → currently in progress / partial match
            * danger    → error encountered
            * secondary → inactive / not reached yet

        GSTR1 Specific:
        - Excludes: 'sending_error', 'waiting_for_status', 'error_in_invoice'
        - 'sending':
            - warning if still processing
            - danger if failed
        - 'sent':
            - success if sent
            - danger if invoice error or waiting with blocking
        - All other active states are success.

        GSTR2B Specific:
        - Excludes: 'fetching', 'error_in_fetching', 'partially_matched'
        - 'fetch':
            - warning if fetching
            - danger if failed
        - 'matched':
            - warning if only partially matched
        - All other active states are success.
        """
        super()._compute_visible_states()
        for record in self:
            new_visible_states = []
            if record.type_external_id in (GSTR1_RETURN_TYPE, GSTR_IFF_RETURN_TYPE):
                for visible_state in record.visible_states:
                    visible_state_name = visible_state.get('name')
                    if visible_state_name not in ['sending_error', 'waiting_for_status', 'error_in_invoice']:
                        if visible_state_name == 'sending' and record.l10n_in_gstr1_status == 'sending':
                            visible_state['alert_type'] = 'warning'
                        elif (
                            visible_state_name == 'sending' and
                            record.l10n_in_gstr1_status == 'sending_error'
                        ) or (
                            visible_state_name == 'sent' and
                            record.l10n_in_gstr1_status == 'error_in_invoice'
                        ) or (
                            visible_state_name == 'sent' and
                            record.l10n_in_gstr1_status == 'waiting_for_status' and
                            record.l10n_in_gstr1_blocking_level
                        ):
                            visible_state['active'] = True
                            visible_state['alert_type'] = 'danger'
                        elif visible_state['active']:
                            visible_state['alert_type'] = 'success'
                        else:
                            visible_state['alert_type'] = '300'
                        new_visible_states.append(visible_state)

            if record.type_external_id == GSTR2B_RETURN_TYPE:
                for visible_state in record.visible_states:
                    visible_state_name = visible_state.get('name')
                    if visible_state_name not in ['fetching', 'error_in_fetching', 'partially_matched']:
                        if (
                            visible_state_name == 'fetch' and
                            record.l10n_in_gstr2b_status == 'fetching'
                        ) or (
                            visible_state_name == 'matched' and
                            record.l10n_in_gstr2b_status == 'partially_matched'
                        ):
                            visible_state['active'] = True
                            visible_state['alert_type'] = 'warning'
                        elif (
                            visible_state_name == 'fetch' and
                            record.l10n_in_gstr2b_status == 'error_in_fetching'
                        ):
                            visible_state['alert_type'] = 'danger'
                        elif visible_state['active']:
                            visible_state['alert_type'] = 'success'
                        else:
                            visible_state['alert_type'] = '300'
                        new_visible_states.append(visible_state)

            if new_visible_states:
                record.visible_states = new_visible_states

    # ===============================
    # GSTR Common Methods
    # ===============================

    @api.depends("date_to")
    def _compute_rtn_period_month_year(self):
        for period in self:
            if period.date_to:
                period.l10n_in_month_year = period.date_to.strftime("%m%Y")
            else:
                period.l10n_in_month_year = False

    @api.model
    def _l10n_in_check_config(self, company=False):
        company = company or self.company_id
        action = False
        button_name = msg = ""
        if not company.partner_id.check_vat_in(company.vat):
            action = {
                'view_mode': 'form',
                'res_model': 'res.company',
                'type': 'ir.actions.act_window',
                'res_id': company.id,
                'views': [[self.env.ref('base.view_company_form').id, 'form']],
            }
            msg = _("Please set a valid GST number on company.")
            button_name = _('Go to Company')
            raise RedirectWarning(msg, action, button_name)
        if not company.sudo().l10n_in_gstr_gst_username:
            msg = _("First setup GST user name and validate using OTP from configuration")
            button_name = _('Go to the configuration panel')
            action = self.env.ref('account.action_account_config').id
        if not company._is_l10n_in_gstr_token_valid():
            context = {
                'default_company_id': company.id,
                'dialog_size': 'medium',
            }
            form = self.env.ref("l10n_in_reports.view_get_otp_gstr_validate_send_otp")
            action = {
                'name': _('OTP Request'),
                'type': 'ir.actions.act_window',
                'res_model': 'l10n_in.gst.otp.validation',
                'views': [[form.id, 'form']],
                'target': 'new',
                'context': context
            }
            msg = _("The NIC portal connection has expired. To re-initiate the connection, you can send an OTP request.")
            button_name = _('Re-Initiate')
        if msg and button_name and action:
            raise RedirectWarning(msg, action, button_name)

    def _cron_refresh_gst_token(self):
        # If Token is already expired than we can't refresh it.
        companies = self.env['res.company'].search([
            ('has_vat', '=', True),
            ('partner_id.country_id.code', '=', 'IN'),
            ('l10n_in_gstr_gst_username', '!=', False),
            ('l10n_in_gst_efiling_feature', '=', True),
        ])
        token_refreshed = False
        for company in companies:
            # Tokens expiring in 6 minutes then refresh it.
            if company._is_l10n_in_gstr_token_valid() and (
                company.l10n_in_gstr_gst_token_validity - fields.Datetime.now()) <= timedelta(minutes=6):
                response = self._l10n_in_refresh_gstr_token_request(company)
                if response.get('error'):
                    message = ''.join([
                        f"<p><b>[{error.get('code', '')}]</b> - <b>{error.get('message', '')}</b></p>"
                        for error in response.get("error", {})])
                    _logger.warning(_('%s', message))
                    continue
                company.l10n_in_gstr_gst_token_validity = fields.Datetime.now() + timedelta(hours=6)
                token_refreshed = True
        # trigger token refresh cron before expired
        if token_refreshed:
            self.env.ref("l10n_in_reports.ir_cron_auto_refresh_gst_token")._trigger(fields.Datetime.now() + timedelta(hours=5, minutes=54))

    def _get_l10n_in_error_level(self, error_codes):
        warning_codes = {
            "RTN_24",  # File Generation is in progress, please try after sometime.
            "404",  # Resource temporarily unavailable / not found
            "RET2B1017",  # GSTR-2B data for the selected period is not yet available. Please try after sometime.
        }
        return "warning" if warning_codes.intersection(error_codes) else "error"

    # ===============================
    # GSTR-1
    # ===============================

    def _get_tax_details_l10n_in(self, domain, batch_size=10**4):
        domain_query = self.env['account.move.line']._search(domain)
        tax_details_query = SQL("""
            SELECT base_line.id AS base_line_id,
                ANY_VALUE(base_line.balance * -1) AS base_amount,
                ANY_VALUE(base_line.move_id) AS move_id,
                ANY_VALUE(base_line.l10n_in_gstr_section) AS l10n_in_gstr_section,
                ANY_VALUE(base_line.l10n_in_hsn_code) AS l10n_in_hsn_code,
                ANY_VALUE(base_line.quantity) AS quantity,
                ANY_VALUE(base_line.product_uom_id) AS product_uom_id,
                ANY_VALUE(base_line.partner_id) AS partner_id,
                ANY_VALUE(move.name) AS invoice_number,
                ANY_VALUE(move.move_type) AS move_type,
                ANY_VALUE(base_line.invoice_date) AS invoice_date,
                -- show positive Total for Invoice and Credit note both so do ABS() to avoid negative value for Credit note
                ANY_VALUE(ABS(move.amount_total_signed)) AS amount_total_signed,
                ANY_VALUE(move.l10n_in_adjustment_type) AS l10n_in_adjustment_type,
                ANY_VALUE(move.l10n_in_state_id) AS l10n_in_state_id,
                ANY_VALUE(move.l10n_in_gst_treatment) AS l10n_in_gst_treatment,
                ANY_VALUE(move.l10n_in_transaction_type) AS l10n_in_transaction_type,
                ANY_VALUE(move.l10n_in_shipping_bill_number) AS shipping_bill_number,
                ANY_VALUE(move.l10n_in_shipping_bill_date) AS shipping_bill_date,
                ANY_VALUE(%(l10n_in_iff_reported)s) AS l10n_in_iff_reported,
                ANY_VALUE(partner.vat) AS customer_gstin,
                ANY_VALUE(pos.l10n_in_tin) AS pos_code,
                ANY_VALUE(uom.l10n_in_code) AS product_uom_code,
                ANY_VALUE(port.code) AS port_code,
                -- aggregate tax amounts
                COALESCE(SUM(tax_details.tax_amount * -1) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(igst_tag)s), 0) AS igst,
                COALESCE(SUM(tax_details.tax_amount * -1) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(cgst_tag)s), 0) AS cgst,
                COALESCE(SUM(tax_details.tax_amount * -1) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(sgst_tag)s), 0) AS sgst,
                COALESCE(SUM(tax_details.tax_amount * -1) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(cess_tag)s), 0) AS cess,
                (
                    COALESCE(MAX(tax.amount) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(igst_tag)s), 0)
                    + COALESCE(MAX(tax.amount) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(cgst_tag)s), 0)
                    + COALESCE(MAX(tax.amount) FILTER (WHERE tax_tag_rel.account_account_tag_id = %(sgst_tag)s), 0)
                ) AS gst_tax_rate
              FROM (%(tax_details_query)s) AS tax_details
              JOIN account_move_line base_line ON base_line.id = tax_details.base_line_id
              JOIN account_move move ON move.id = base_line.move_id
              JOIN res_country_state pos ON pos.id = move.l10n_in_state_id
              JOIN res_partner partner ON partner.id = base_line.partner_id
         LEFT JOIN uom_uom uom ON uom.id = base_line.product_uom_id
         LEFT JOIN l10n_in_port_code port ON port.id = move.l10n_in_shipping_port_code_id
         LEFT JOIN account_tax tax ON tax.id = tax_details.tax_id
         LEFT JOIN account_account_tag_account_tax_repartition_line_rel tax_tag_rel
                   ON tax_tag_rel.account_tax_repartition_line_id = tax_details.tax_repartition_line_id
                   AND tax_tag_rel.account_account_tag_id IN (%(igst_tag)s, %(cgst_tag)s, %(sgst_tag)s, %(cess_tag)s)
             WHERE base_line.tax_repartition_line_id IS NULL
         GROUP BY base_line.id
            """,
            tax_details_query=self.env['account.move.line']._get_query_tax_details(domain_query, include_without_tax_line=True),
            l10n_in_iff_reported=self.env['account.move']._get_l10n_in_iff_reported_query('move'),
            igst_tag=self.env.ref('l10n_in.tax_tag_igst').id,
            cgst_tag=self.env.ref('l10n_in.tax_tag_cgst').id,
            sgst_tag=self.env.ref('l10n_in.tax_tag_sgst').id,
            cess_tag=self.env.ref('l10n_in.tax_tag_cess').id,
        )
        # Use a separate cursor for batch processing, as intermediate ORM query processing may override cursor results,
        # but reuse the existing environment cursor during tests to maintain transaction isolation.
        if config.get('test_enable'):
            self.env.cr.execute(tax_details_query)
            yield from self.env.cr.dictfetchall()
        else:
            with self.env.registry.cursor() as cr:
                cr.execute(tax_details_query)
                while tax_details := cr.dictfetchmany(batch_size):
                    yield from tax_details

    def _convert_gstr1_indexed_data_to_json(self, gstr1_index_json):
        """
        Convert the internally indexed GSTR-1 data into the final GSTR-1
        JSON format by removing temporary indexes and converting dictionaries
        to the list-based structure expected by GSTR-1.
        """

        def _convert_items(invoice_data, section):
            """
            Convert the indexed `itms` dictionary into the GSTR-1 item format.

            For B2B, B2CL, CDNR and CDNUR:
                {18: {'rate': 18.0, ...}}
                ->
                [{'num': 1, 'itm_det': {'rate': 18.0, ...}}]

            For EXP:
                {18: {'rt': 18.0, ...}}
                ->
                [{'rt': 18.0, ...}]
            """
            for data in invoice_data:
                items = data['itms'].values()

                if section == 'exp':
                    data['itms'] = list(items)
                else:
                    data['itms'] = [
                        {'num': num, 'itm_det': item}
                        for num, item in enumerate(items, start=1)
                    ]

        def _convert_invoice_section(section, section_data):
            """
            Convert invoice-based sections into the GSTR-1 structure.

            B2B:
                customer GSTIN -> invoices
                {ctin: ..., inv: [...]}

            B2CL:
                POS -> invoices
                {pos: ..., inv: [...]}

            CDNR:
                customer GSTIN -> notes
                {ctin: ..., nt: [...]}

            EXP:
                export type -> invoices
                {exp_typ: ..., inv: [...]}
            """
            for grouped_data in section_data.values():
                _convert_items(grouped_data.values(), section)

            group_key = {
                'b2b': 'ctin',
                'b2cl': 'pos',
                'cdnr': 'ctin',
                'exp': 'exp_typ',
            }[section]

            invoice_key = 'nt' if section == 'cdnr' else 'inv'

            return [
                {
                    group_key: group_value,
                    invoice_key: list(grouped_data.values()),
                }
                for group_value, grouped_data in section_data.items()
            ]

        def _convert_b2cs(section_data):
            """
            Convert B2CS data by removing its temporary grouping index.

            Input:
                {'24-5': {...}}

            Output:
                [{...}]
            """
            return list(section_data.values())

        def _convert_cdnur(section_data):
            """
            Convert CDNUR notes from indexed dictionaries to a list and
            convert their indexed `itms` into the standard GSTR-1 item format.
            """
            _convert_items(section_data.values(), 'cdnur')
            return list(section_data.values())

        def _convert_nil(section_data):
            """
            Convert NIL data into the GSTR-1 structure.

            Input:
                {'INTRB2B/INTRB2C/...': {...}}

            Output:
                {'inv': [{...}]}
            """
            return {'inv': list(section_data.values())}

        def _convert_hsn(section_data):
            """
            Convert HSN data by removing the temporary HSN index and adding
            the sequential `num` required by the GSTR-1 format.

            Input:
                {
                    'hsn_b2b': {
                        '94038900_UNT_5': {...}
                    }
                }

            Output:
                {
                    'hsn_b2b': [
                        {'num': 1, ...}
                    ]
                }
            """
            return {
                hsn_section: [
                    {
                        'num': num,
                        **hsn_data,
                    }
                    for num, hsn_data in enumerate(
                        hsn_data_by_index.values(),
                        start=1,
                    )
                ]
                for hsn_section, hsn_data_by_index in section_data.items()
            }

        # Invoice-based sections.
        for section in ('b2b', 'b2cl', 'cdnr', 'exp'):
            if section in gstr1_index_json:
                gstr1_index_json[section] = _convert_invoice_section(
                    section,
                    gstr1_index_json[section],
                )

        # B2CS contains flat records without `itms`.
        if 'b2cs' in gstr1_index_json:
            gstr1_index_json['b2cs'] = _convert_b2cs(
                gstr1_index_json['b2cs'],
            )

        # CDNUR contains notes with indexed `itms`.
        if 'cdnur' in gstr1_index_json:
            gstr1_index_json['cdnur'] = _convert_cdnur(
                gstr1_index_json['cdnur'],
            )

        # NIL contains flat records grouped by supply type.
        if 'nil' in gstr1_index_json:
            gstr1_index_json['nil'] = _convert_nil(
                gstr1_index_json['nil'],
            )

        # HSN contains records grouped by HSN section.
        if 'hsn' in gstr1_index_json:
            gstr1_index_json['hsn'] = _convert_hsn(
                gstr1_index_json['hsn'],
            )

        return gstr1_index_json

    def _get_l10n_in_gstr1_json(self):
        """
        This method is return gstr1 json from tax_details_query
        - B2B and CDNR it's group by gstin, invoice number and GST tax rate
        - B2CL it's group by Place of Supply, invoice number and GST tax rate
        - B2CS it's group by place of supply, GST tax rate
        - CDNUR it's group by invoice number and GST tax rate
        - EXP it's group by Export type, invoice number and GST tax rate
        - Nil rated, exempted and non-gst supplies it's group by Base Tags
        - HSN - it's group by GST treatment type(B2B, B2C), HSN, UQC and GST tax rate
        """
        section_func_map = {
            **dict.fromkeys((
                'sale_b2b_rcm',
                'sale_b2b_regular',
                'sale_deemed_export',
                'sale_sez_wp',
                'sale_sez_wop',
            ), self._l10n_in_process_b2b_json),
            'sale_b2cl': self._l10n_in_process_b2cl_json,
            'sale_b2cs': self._l10n_in_process_b2cs_json,
            **dict.fromkeys((
                'sale_cdnr_rcm',
                'sale_cdnr_regular',
                'sale_cdnr_deemed_export',
                'sale_cdnr_sez_wp',
                'sale_cdnr_sez_wop',
            ), self._l10n_in_process_cdnr_json),
            **dict.fromkeys((
                'sale_cdnur_b2cl',
                'sale_cdnur_exp_wp',
                'sale_cdnur_exp_wop',
            ), self._l10n_in_process_cdnur_json),
            **dict.fromkeys((
                'sale_exp_wp',
                'sale_exp_wop',
            ), self._l10n_in_process_exp_json),
            **dict.fromkeys((
                'sale_nil_rated',
                'sale_exempt',
                'sale_non_gst_supplies',
            ), self._l10n_in_process_nongst_json),
        }

        gstr1_index_json = {}
        is_iff_return = self.type_external_id == GSTR_IFF_RETURN_TYPE
        for tax_details in self._get_tax_details_l10n_in(self._get_tax_detail_domain(is_iff_return)):
            if section_func := section_func_map.get(tax_details['l10n_in_gstr_section']):
                section_func(gstr1_index_json, tax_details)
            if not is_iff_return:
                self._l10n_in_process_hsn_json(gstr1_index_json, tax_details)
        # this is not set from account.move.line, we have different model for this, so we need to set it separately
        if not is_iff_return:
            gstr1_index_json['doc_issue'] = self._get_l10n_in_doc_issue_json()
        gstr1_index_json['gstin'] = self.tax_unit_id.vat or self.company_id.vat
        gstr1_index_json['fp'] = self.l10n_in_month_year
        return self._convert_gstr1_indexed_data_to_json(gstr1_index_json)

    def _l10n_in_process_b2b_json(self, gstr1_json, tax_details):
        """
            This method is process b2b json from tax_details
            it's add b2b details in gstr1_json
            Here itms is group by GST number, invoice number and GST tax rate
            it's add in gstr1_json as below
            {
                'b2b': {
                    '24AACCT6304M1ZB': {
                        5: {
                            'inum': 'INV/2022/00005',
                            'idt': '01-04-2022',
                            'val': 100.00,
                            'pos': '24',
                            'rchrg': 'N',
                            'inv_typ': 'R',
                            'etin': "34AACCT6304M1ZB",
                            'itms': {
                                18: {
                                    'rate': 18.0,
                                    'txval': 100.0,
                                    'iamt': 0.0,
                                    'samt': 9.0,
                                    'camt': 9.0,
                                    'csamt': 6.5
                                }
                            }
                        }
                    }
                }
            }
        """
        if (
            self.type_id._get_periodicity(self.company_id) == 'trimester'
            and self.type_external_id == GSTR1_RETURN_TYPE
            and tax_details['l10n_in_iff_reported']
        ):
            return
        gstin = tax_details['customer_gstin']
        rate = tax_details['gst_tax_rate']
        invoice_type = 'R'
        if tax_details['l10n_in_gstr_section'] == 'sale_sez_wp':
            invoice_type = 'SEWP'
        elif tax_details['l10n_in_gstr_section'] == 'sale_sez_wop':
            invoice_type = 'SEWOP'
        elif tax_details['l10n_in_gstr_section'] == 'sale_deemed_export':
            invoice_type = 'DE'
        b2b_data = gstr1_json.setdefault('b2b', {}).setdefault(gstin, {}).setdefault(tax_details['move_id'], {
            'inum': tax_details['invoice_number'],
            'idt': tax_details['invoice_date'].strftime('%d-%m-%Y'),
            'val': tax_details['amount_total_signed'],
            'pos': tax_details['pos_code'],
            'rchrg': 'Y' if tax_details['l10n_in_gstr_section'] == 'sale_b2b_rcm' else 'N',
            'inv_typ': invoice_type,
            'itms': {}
        })
        b2b_data['itms'].setdefault(rate, {'rt': rate, 'txval': 0.0, 'iamt': 0.0, 'camt': 0.0, 'samt': 0.0, 'csamt': 0.0})
        b2b_data['itms'][rate]['txval'] += tax_details['base_amount']
        b2b_data['itms'][rate]['iamt'] += tax_details['igst']
        b2b_data['itms'][rate]['camt'] += tax_details['cgst']
        b2b_data['itms'][rate]['samt'] += tax_details['sgst']
        b2b_data['itms'][rate]['csamt'] += tax_details['cess']

    def _l10n_in_process_b2cl_json(self, gstr1_json, tax_details):
        """
            This method is process b2cl json from tax_details
            it's add b2cl details in gstr1_json
            Here itms is group by Place of Supply, invoice number and GST tax rate
            it's add in gstr1_json as below
            {
                'b2cl': {
                    '24': {
                        5: {
                            'inum': 'INV/2022/00005',
                            'idt': '01-04-2022',
                            'val': 100.00,
                            'itms': {
                                18: {
                                    'rate': 18.0,
                                    'txval': 100.0,
                                    'iamt': 0.0,
                                    'samt': 9.0,
                                    'camt': 9.0,
                                    'csamt': 6.5
                                }
                            }
                        }
                    }
                }
            }
        """
        pos = tax_details['pos_code']
        rate = tax_details['gst_tax_rate']
        b2cl_data = gstr1_json.setdefault('b2cl', {}).setdefault(pos, {}).setdefault(tax_details['move_id'], {
            'inum': tax_details['invoice_number'],
            'idt': tax_details['invoice_date'].strftime('%d-%m-%Y'),
            'val': tax_details['amount_total_signed'],
            'itms': {}
        })
        b2cl_data['itms'].setdefault(rate, {
            'rt': rate, 'txval': 0.0, 'iamt': 0.0, 'csamt': 0.0
        })
        b2cl_data['itms'][rate]['txval'] += tax_details['base_amount']
        b2cl_data['itms'][rate]['iamt'] += tax_details['igst']
        b2cl_data['itms'][rate]['csamt'] += tax_details['cess']

    def _l10n_in_process_b2cs_json(self, gstr1_json, tax_details):
        """
            This method is process b2cs json from tax_details
            it's add b2cs details in gstr1_json
            Here itms is group by Place of Supply, GST tax rate
            it's add in gstr1_json as below
            {
                'b2cs': {
                    '24-5': {
                        'sply_ty': 'INTRA/INTER',
                        'pos': '36',
                        'typ': 'OE',
                        'rt': 5.0,
                        'txval': 100.0,
                        'iamt': 0.0,
                        'samt': 9.0,
                        'camt': 9.0,
                        'csamt': 6.5
                    }
                }
            }
        """
        pos = tax_details['pos_code']
        rate = tax_details['gst_tax_rate']
        grouping_key = f"{pos}-{rate}"
        b2cs_data = gstr1_json.setdefault('b2cs', {}).setdefault(grouping_key, {
            'sply_ty': 'INTER' if tax_details['l10n_in_transaction_type'] == 'inter_state' else 'INTRA',
            'typ': 'OE', 'pos': pos, 'rt': rate, 'txval': 0.0,
            'iamt': 0.0, 'camt': 0.0, 'samt': 0.0, 'csamt': 0.0
        })
        b2cs_data['txval'] += tax_details['base_amount']
        b2cs_data['iamt'] += tax_details['igst']
        b2cs_data['camt'] += tax_details['cgst']
        b2cs_data['samt'] += tax_details['sgst']
        b2cs_data['csamt'] += tax_details['cess']

    def _l10n_in_process_cdnr_json(self, gstr1_json, tax_details):
        """
            This method is process cdnr json from tax_details
            it's add cdnr details in gstr1_json
            Here itms is group by GST number, invoice number and GST tax rate
            it's add in gstr1_json as below
            {
                'cdnr': {
                    '24AACCT6304M1ZB': {
                        5: {
                            'ntty': 'C',
                            'nt_num': 'RINV/2022/00001',
                            'nt_dt': '02-04-2022',
                            'val': 105296.77,
                            'pos': '24',
                            'rchrg': 'N',
                            'inv_typ': 'R',
                            'itms`: {
                                18:{
                                    'rt': 18.0,
                                    'txval': 180000.0,
                                    'iamt': 32400.0,
                                    'csamt': 0.0
                                }
                            }
                        }
                    }
                }
            }
        """
        if (
            self.type_id._get_periodicity(self.company_id) == 'trimester'
            and self.type_external_id == GSTR1_RETURN_TYPE
            and tax_details['l10n_in_iff_reported']
        ):
            return
        gstin = tax_details['customer_gstin']
        rate = tax_details['gst_tax_rate']
        invoice_type = 'R'
        if tax_details['l10n_in_gstr_section'] == 'sale_cdnr_sez_wp':
            invoice_type = 'SEWP'
        elif tax_details['l10n_in_gstr_section'] == 'sale_cdnr_sez_wop':
            invoice_type = 'SEWOP'
        elif tax_details['l10n_in_gstr_section'] == 'sale_cdnr_deemed_export':
            invoice_type = 'DE'
        cdnr_data = gstr1_json.setdefault('cdnr', {}).setdefault(gstin, {}).setdefault(tax_details['move_id'], {
            'ntty': 'C' if tax_details['move_type'] == 'out_refund' else 'D',
            'nt_num': tax_details['invoice_number'],
            'nt_dt': tax_details['invoice_date'].strftime('%d-%m-%Y'),
            'val': tax_details['amount_total_signed'],
            'pos': tax_details['pos_code'],
            'inv_typ': invoice_type,
            'rchrg': 'Y' if tax_details['l10n_in_gstr_section'] == 'sale_cdnr_rcm' else 'N',
            'itms': {}
        })
        cdnr_data['itms'].setdefault(rate, {'rt': rate, 'txval': 0.0, 'iamt': 0.0, 'camt': 0.0, 'samt': 0.0, 'csamt': 0.0})
        sign = -1 if tax_details['move_type'] == 'out_refund' else 1
        cdnr_data['itms'][rate]['txval'] += tax_details['base_amount'] * sign
        cdnr_data['itms'][rate]['iamt'] += tax_details['igst'] * sign
        cdnr_data['itms'][rate]['camt'] += tax_details['cgst'] * sign
        cdnr_data['itms'][rate]['samt'] += tax_details['sgst'] * sign
        cdnr_data['itms'][rate]['csamt'] += tax_details['cess'] * sign

    def _l10n_in_process_cdnur_json(self, gstr1_json, tax_details):
        """
            This method is process cdnur json from tax_details
            it's add cdnur details in gstr1_json
            Here itms is group by invoice number and GST tax rate
            it's add in gstr1_json as below
            {
                'cdnur': {
                    5: {
                        'ntty': 'C',
                        'nt_num': 'RINV/2022/00002',
                        'nt_dt': '02-05-2022',
                        'val': 212400.0,
                        'pos': '30',
                        'typ': 'B2CL',
                        'itms`: {
                            18:{
                                'rt': 18.0,
                                'txval': 180000.0,
                                'iamt': 32400.0,
                                'csamt': 0.0
                            }
                        }
        """
        rate = tax_details['gst_tax_rate']
        invoice_type = 'B2CL'
        if tax_details['l10n_in_gstr_section'] == 'sale_cdnur_exp_wp':
            invoice_type = 'EXPWP'
        elif tax_details['l10n_in_gstr_section'] == 'sale_cdnur_exp_wop':
            invoice_type = 'EXPWOP'
        move_defaults = {
            'ntty': 'C' if tax_details['move_type'] == 'out_refund' else 'D',
            'nt_num': tax_details['invoice_number'],
            'nt_dt': tax_details['invoice_date'].strftime('%d-%m-%Y'),
            'val': tax_details['amount_total_signed'],
            'typ': invoice_type,
            'itms': {}
        }
        if invoice_type == 'B2CL':
            move_defaults['pos'] = tax_details['pos_code']
        cdnur_data = gstr1_json.setdefault('cdnur', {}).setdefault(tax_details['move_id'], move_defaults)
        cdnur_data['itms'].setdefault(rate, {
            'rt': rate, 'txval': 0.0, 'iamt': 0.0, 'csamt': 0.0
        })
        sign = -1 if tax_details['move_type'] == 'out_refund' else 1
        # For Export with payment add tax values invoice total
        if invoice_type == 'EXPWP':
            cdnur_data['val'] += (tax_details['igst'] + tax_details['cess']) * sign
        cdnur_data['itms'][rate]['txval'] += tax_details['base_amount'] * sign
        cdnur_data['itms'][rate]['iamt'] += tax_details['igst'] * sign
        cdnur_data['itms'][rate]['csamt'] += tax_details['cess'] * sign

    def _l10n_in_process_exp_json(self, gstr1_json, tax_details):
        """
            This method is process exp json from tax_details
            it's add exp details in gstr1_json
            Here itms is group by Export type, invoice number and GST tax rate
            it's add in gstr1_json as below
            {
                'exp': {
                    'WPAY': {
                        '5': {
                            'inum': 'INV/2022/00008',
                            'idt': '01-04-2022',
                            'val': 283200.0,
                            'sbnum': '999704',
                            'sbdt': '02/04/2022',
                            'sbpcode': 'INIXY1',
                            'itms': {
                                '18': {
                                    'rt': 18.0,
                                    'txval': 240000.0,
                                    'iamt': 43200.0,
                                    'csamt': 0.0
                                }
                            }
                        }
                    }
                }
            }
        """
        exp_type = 'WPAY' if tax_details['l10n_in_gstr_section'] == 'sale_exp_wp' else 'WOPAY'
        rate = tax_details['gst_tax_rate']
        move_defaults = {
            'inum': tax_details['invoice_number'],
            'idt': tax_details['invoice_date'].strftime('%d-%m-%Y'),
            'val': tax_details['amount_total_signed'],
            'itms': {}
        }
        if tax_details['shipping_bill_number']:
            move_defaults['sbnum'] = tax_details['shipping_bill_number']
        if tax_details['shipping_bill_date']:
            move_defaults['sbdt'] = tax_details['shipping_bill_date'].strftime('%d-%m-%Y')
        if tax_details['port_code']:
            move_defaults['sbpcode'] = tax_details['port_code']
        exp_data = gstr1_json.setdefault('exp', {}).setdefault(exp_type, {}).setdefault(tax_details['move_id'], move_defaults)
        exp_data['itms'].setdefault(rate, {
            'rt': rate, 'txval': 0.0, 'iamt': 0.0, 'csamt': 0.0
        })
        # If Base amount and Invoice total is same then add tax values in total for Export with payment only
        if exp_type == 'WPAY':
            exp_data['val'] += tax_details['igst'] + tax_details['cgst']
        exp_data['itms'][rate]['txval'] += tax_details['base_amount']
        exp_data['itms'][rate]['iamt'] += tax_details['igst']
        exp_data['itms'][rate]['csamt'] += tax_details['cess']

    def _l10n_in_process_nongst_json(self, gstr1_json, tax_details):
        """
            This method is process non-gst json from tax_details
            it's add non-gst details in gstr1_json
            Here itms is group by Base Tags
            it's add in gstr1_json as below
            {
                'nil': {
                    'INTRB2B/INTRB2C/INTRAB2B/INTRAB2C': {
                        'nil_amt': 100.0,
                        'expt_amt': 200.0,
                        'ngsup_amt': 300.0,
                    }
                }
            }
        """
        is_b2b = tax_details.get('l10n_in_gst_treatment') in {
            'regular', 'composition', 'deemed_export', 'uin_holders', 'special_economic_zone'}
        if tax_details.get('l10n_in_transaction_type') == 'inter_state':
            supply_type = 'INTRB2B' if is_b2b else 'INTRB2C'
        else:
            supply_type = 'INTRAB2B' if is_b2b else 'INTRAB2C'

        inv_data = gstr1_json.setdefault('nil', {}).setdefault(supply_type, {
            'sply_ty': supply_type,
            'nil_amt': 0.0,
            'expt_amt': 0.0,
            'ngsup_amt': 0.0,
        })
        if tax_details['l10n_in_gstr_section'] == 'sale_nil_rated':
            inv_data['nil_amt'] += tax_details['base_amount']
        elif tax_details['l10n_in_gstr_section'] == 'sale_exempt':
            inv_data['expt_amt'] += tax_details['base_amount']
        elif tax_details['l10n_in_gstr_section'] == 'sale_non_gst_supplies':
            inv_data['ngsup_amt'] += tax_details['base_amount']

    def _l10n_in_process_hsn_json(self, gstr1_json, tax_details):
        """
            This method is process hsn json from tax_details
            it's add hsn details in gstr1_json
            Here invoice lines are grouped by GST treatment type, product HSN code, product unit code and GST tax rate.
            it's add in gstr1_json as below
            { 'hsn': {
                'hsn_b2b/hsn_b2c': {
                    '94038900_UNT_5': {
                        'num': 1,
                        'hsn_sc': '94038900',
                        'uqc': 'UNT',
                        'rt': 5.0,
                        'qty': 10.0,
                        'txval': 40000.0,
                        'iamt': 0.0,
                        'samt': 1000.0,
                        'camt': 1000.0,
                        'csamt': 0.0
                    }
                }
            }
        """
        if tax_details['l10n_in_gst_treatment'] in {
            'regular', 'composition', 'deemed_export', 'uin_holders', 'special_economic_zone'}:
            hsn_type = 'hsn_b2b'
        elif not self.company_id.l10n_in_disable_b2c_hsn_reporting:
            hsn_type = 'hsn_b2c'
        else:
            return
        gst_rate = tax_details['gst_tax_rate']
        uqc = (
            tax_details['product_uom_code']
            and tax_details['product_uom_code'].split("-")[0]
            or "OTH"
        )
        if is_service_line := self.env['account.move']._l10n_in_is_service_hsn(tax_details['l10n_in_hsn_code']):
            # If product is service then UQC is Not Applicable (NA)
            uqc = "NA"
        hsn_group_key = f"{tax_details['l10n_in_hsn_code']}_{uqc}_{gst_rate}"
        hsn_data = gstr1_json.setdefault('hsn', {}).setdefault(hsn_type, {}).setdefault(hsn_group_key, {
            'hsn_sc': tax_details['l10n_in_hsn_code'],
            'uqc': uqc,
            'rt': int(gst_rate) if gst_rate.is_integer() else gst_rate,
            'qty': 0.0,
            'txval': 0.0,
            'iamt': 0.0,
            'samt': 0.0,
            'camt': 0.0,
            'csamt': 0.0,
        })
        # Price adjustment credit / debit notes are to adjust total amounts they do not alter quantity,
        # so they are excluded from HSN quantity calculations.
        if not (is_service_line or tax_details['l10n_in_adjustment_type'] == 'price_adjustment'):
            if tax_details['move_type'] in ('out_refund', 'in_refund'):
                hsn_data['qty'] -= tax_details['quantity']
            else:
                hsn_data['qty'] += tax_details['quantity']
        hsn_data['txval'] += tax_details['base_amount']
        hsn_data['iamt'] += tax_details['igst']
        hsn_data['samt'] += tax_details['cgst']
        hsn_data['camt'] += tax_details['sgst']
        hsn_data['csamt'] += tax_details['cess']

    def _get_l10n_in_doc_issue_json(self):
        """
        This method returns the doc_issue JSON (Table 13) as below.
        Here, data is grouped by nature of document and serial range.
            {
            'doc_det': [{
                    'doc_num': 1,
                    'docs': [
                        {
                            'num': 1,
                            'from': invoice.name,
                            'to': invoice.name,
                            'totnum': 1,
                            'cancel': 0,
                            'net_issue': 1,
                        }
                    ]
                }]
            }
        """
        doc_map = defaultdict(list)
        for line in self.l10n_in_doc_summary_line_ids:
            doc_map[int(line.nature_of_document)].append(line)
        doc_det = [
            {
                'doc_num': doc_num,
                'docs': [
                    {
                        'num': idx,
                        'from': line.serial_from,
                        'to': line.serial_to,
                        'totnum': line.total_issued,
                        'cancel': line.total_cancelled,
                        'net_issue': line.total_issued - line.total_cancelled,
                    } for idx, line in enumerate(lines, 1)
                ]
            } for doc_num, lines in sorted(doc_map.items())
        ]
        return {'doc_det': doc_det}

    def action_l10n_in_send_gstr1(self):
        """ checks the validations and trigger the cron to send the GSTR-1 data
        """
        cron = self.env.ref('l10n_in_reports.ir_cron_to_send_gstr1_data')
        cron_sudo = cron.sudo()
        if not cron_sudo.active:
            if self.env.user.has_group('base.group_system'):
                message = _("Can not send GSTR-1 data because the required scheduled action '%s' is not active.", cron_sudo.cron_name)
                action = {
                    'name': _("Scheduled Action"),
                    'type': 'ir.actions.act_window',
                    'res_model': 'ir.cron',
                    'res_id': cron.id,
                    'views': [[False, 'form']],
                }
                raise RedirectWarning(message, action, _("Go to Scheduled Action"))
            else:
                raise ValidationError(_("Can not send GSTR-1 data because the required scheduled action '%s' is not active.\nPlease contact your system administrator.", cron_sudo.cron_name))

        self._l10n_in_check_config()
        if not self.env['account.move.line'].sudo().search_count(self._get_tax_detail_domain(), limit=1):
            raise ValidationError(_("There are no transactions available for the current period to send for GSTR-1 filing."))
        self.sudo().write({
            "l10n_in_gstr1_blocking_level": False,
            "state": "sending",
        })
        cron._trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'message': _("Action triggered — now waiting in queue to prepare and send data."),
                'sticky': True,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def _cron_send_gstr1_data(self, job_count=None):
        gstr1_sending = self.search([
            ("l10n_in_gstr1_status", "=", "sending"),
            ("l10n_in_gstr1_blocking_level", "!=", "error"),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
        ])
        process_gstr1 = gstr1_sending[:job_count] if job_count else gstr1_sending
        for return_period in process_gstr1:
            return_period._l10n_in_send_gstr1()
            if len(process_gstr1) > 1:
                self.env.cr.commit()
        if process_gstr1:
            self.env.ref("l10n_in_reports.ir_cron_to_check_gstr1_status")._trigger(fields.Datetime.now() + timedelta(minutes=1))
        if len(process_gstr1) != len(gstr1_sending):
            self.env.ref("l10n_in_reports.ir_cron_to_send_gstr1_data")._trigger()

    def _l10n_in_send_gstr1(self):
        """Send GSTR-1 data to the government portal.
        This method prepares the GSTR-1 JSON payload, attaches it to the return record,
        and sends it to the government portal.
        """
        _ = self.env._
        if not self.company_id._is_l10n_in_gstr_token_valid():
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
                "state": "sending_error",
            })
            msg = _("GSTR-1/IFF submission failed:  GST token expired or missing, Please regenerate it by verifying GST OTP.")
            self.message_post(body=msg)
            return
        error_msg = ""
        json_payload = self._get_l10n_in_gstr1_json()
        self.sudo().message_post(
            subject=_("GSTR-1/IFF Send data"),
            body=_("Attached JSON file contains the submitted GSTR-1/IFF data."),
            attachments=[("status_response.json", json.dumps(json_payload))])

        # Attach the PDF File
        options = self._get_closing_report_options()
        if self.type_external_id == GSTR_IFF_RETURN_TYPE:
            filename = 'gstr_iff_%s_report.pdf' % self.l10n_in_month_year
        else:
            filename = 'gstr1_%s_report.pdf' % self.l10n_in_month_year
        pdf_content = self.type_id.report_id.with_company(self.company_id).export_to_pdf(options)
        pdf_base64 = pdf_content.get("file_content")
        self.sudo().message_post(
            subject=_("PDF file for GSTR-1/IFF return"),
            body=_("PDF file for GSTR-1/IFF return is attached here"),
            attachments=[(filename, pdf_base64)],
        )

        response = self._l10n_in_send_gstr1_request(
            company=self.company_id,
            json_payload=json_payload,
            month_year=self.l10n_in_month_year)

        if response.get("data"):
            self.sudo().write({
                "l10n_in_gstr_reference": response["data"].get("reference_id"),
                "state": "waiting_for_status",
            })
        elif response.get("error"):
            error_codes = [e.get('code') for e in response["error"]]
            if 'no-credit' in error_codes:
                error_msg = self.env["account.move"]._l10n_in_edi_get_iap_buy_credits_message()
            else:
                error_msg = "<br/>".join(["[%s] %s" % (e.get("code"), html_escape(e.get("message"))) for e in response["error"]])
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": self._get_l10n_in_error_level(error_codes),
                "state": "sending_error",
            })
        else:
            error_msg = _("Something is wrong in response. Please contact support.\n response: %(response)s", response=response)
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
                "state": "sending_error",
            })

        if self.l10n_in_gstr1_blocking_level:
            self.message_post(body=error_msg)
            act_type_xmlid = 'l10n_in_reports.mail_activity_type_gstr1_errors'
            advisor_user = self._get_gstr_responsible_activity_and_user(act_type_xmlid)
            self.activity_schedule(
                act_type_xmlid=act_type_xmlid,
                user_id=advisor_user.id,
                note=_('Solve GSTR-1 Error')
            )

    def _get_gstr_responsible_activity_and_user(self, act_type_xmlid):
        """
        Retrieve the mail activity type for GSTR-1 exceptions and identify the responsible user.
        """
        act_type = self.env.ref(act_type_xmlid, raise_if_not_found=False)
        if not act_type:
            return

        # Determine the responsible user
        advisor_user = self.env['res.users']
        company_ids = self.company_ids or self.company_id
        if (
            act_type and act_type.default_user_id and
            act_type.default_user_id.has_group(self.env.ref('account.group_account_manager').id) and
            any(company in act_type.default_user_id.company_ids for company in company_ids)
        ):
            advisor_user = act_type.default_user_id
        else:
            field_id = self.env['ir.model.fields']._get('account.return', 'l10n_in_gstr1_status')
            # Search for the last relevant mail message to find a responsible user
            last_message = self.env['mail.message'].sudo().search([
                ('model', '=', self._name),
                ('res_id', '=', self.id),
                ('create_uid', '!=', SUPERUSER_ID),
                ('create_uid.all_group_ids', 'in', self.env.ref('account.group_account_manager').ids),
                ('body', 'ilike', field_id.field_description),
                ('message_type', '=', 'tracking'),
            ], limit=1)
            advisor_user = last_message and last_message.create_uid or self.env.user

        return advisor_user

    def check_l10n_in_gstr1_status(self):
        """Check GSTR-1 status and update return record accordingly.
        Following status are handled:
        - P: Processed (success)
        - IP: In Process (waiting)
        - PE: Processed with Error (error in invoice)
        - ER: Error in Response (error in response)
        - Other: Error (unknown status)
        """
        _ = self.env._
        if not self.company_id._is_l10n_in_gstr_token_valid():
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
            })
            msg = _("GSTR-1/IFF check status failed: GST token expired or missing, Please regenerate it by verifying GST OTP.")
            self.message_post(body=msg)
            return
        error_msg = ""
        response = self._l10n_in_get_gstr_status_request(
            company=self.company_id, month_year=self.l10n_in_month_year, reference_id=self.l10n_in_gstr_reference)

        if response.get('data'):
            data = response["data"]
            if data.get("status_cd") == "P":
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": False,
                    "state": "sent",
                    "date_submission": fields.Date.context_today(self)
                })
                odoobot = self.env.ref('base.partner_root')
                self.sudo().message_post(body=_("GSTR-1/IFF Successfully Sent"), author_id=odoobot.id)
            elif data.get("status_cd") == "IP":
                error_msg = _("Waiting for GSTR-1/IFF processing, try in a few minutes")
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": "warning"
                })
            elif data.get("status_cd") in ("PE", "ER"):
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": False,
                    "state": "error_in_invoice"
                })
                message = ""
                act_type_xmlid = 'l10n_in_reports.mail_activity_type_gstr1_exception_to_be_sent'
                AccountMove = self.env['account.move'].with_context(allowed_company_ids=self.company_ids.ids)
                if data.get("status_cd") == "ER":
                    error_report = data.get('error_report', {})
                    message = "[%s] %s" % (error_report.get('error_cd'), error_report.get('error_msg'))
                else:
                    advisor_user = self._get_gstr_responsible_activity_and_user(act_type_xmlid)
                    error_report_summary = {}
                    invoices_to_fetch = set()
                    for section_code, error_items in data.get('error_report', {}).items():
                        error_report_summary[section_code] = {}
                        for error_item in error_items:
                            error_code = error_item.get('error_cd', False)
                            error_message = error_item.get('error_msg', False)
                            invoice_number = None
                            hsn_code = None
                            if error_code or error_message:
                                # Extract invoice number or hsn code based on section_code type
                                if section_code in ('b2b', 'b2cl', 'exp'):
                                    invoice_number = error_item.get('inv')[0].get('inum')
                                if section_code == 'cdnr':
                                    invoice_number = error_item.get('nt')[0].get('nt_num')
                                if section_code == 'cdnur':
                                    invoice_number = error_item.get('nt_num')
                                if section_code == 'hsn':
                                    hsn_code = next(
                                        (
                                            error_item.get(hsn_type)[0].get('hsn_sc')
                                            for hsn_type in ['hsn_b2b', 'hsn_b2c']
                                            if hsn_type in error_item
                                        ),
                                        False,
                                    )
                                # error_key: invoice number for invoice sections (b2b, b2cl, cdnr, ...); error description otherwise
                                # summary_value: error description for invoice sections; hsn_code for hsn section; None otherwise
                                error_key = f"[{error_code}] {error_message}"
                                summary_value = None
                                if invoice_number:
                                    error_key, summary_value = invoice_number, error_key
                                    invoices_to_fetch.add(invoice_number)
                                elif hsn_code:
                                    summary_value = hsn_code

                                error_report_summary[section_code].setdefault(error_key, set())
                                if summary_value:
                                    error_report_summary[section_code][error_key].add(summary_value)
                    # fetch invoices
                    invoice_by_name = AccountMove.search([
                        ('name', 'in', invoices_to_fetch),
                        ('company_id', 'in', self.company_ids.ids or self.company_id.ids)
                    ]).grouped('name')
                    # Generate error messages and schedule activities
                    for section_code, section_errors in error_report_summary.items():
                        message += Markup("<li><b>%s :- </b></li>") % section_code.upper()
                        for error_key, summary_values in section_errors.items():
                            error_note = Markup().join(Markup("<ul><li>%s</li></ul>") % summary_value for summary_value in summary_values)
                            if invoice := invoice_by_name.get(error_key):
                                # Generate a clickable link for the account moves
                                invoice = invoice[:1]
                                message += Markup(
                                    "<ul><li>%s</li>%s</ul>"
                                ) % (invoice._get_html_link(invoice.name), error_note)
                                invoice.activity_schedule(
                                    act_type_xmlid=act_type_xmlid,
                                    user_id=advisor_user.id,
                                    note=_('GSTR-1 Processed with Error: %s', error_note)
                                )
                            else:
                                message += Markup("<ul><li>%s</li>%s</ul>") % (error_key, error_note)
                self.sudo().message_post(
                    subject=_("GSTR-1/IFF Errors"),
                    body=_('%s', message),
                    attachments=[("status_response.json", json.dumps(response))])
            else:
                error_msg = _("Something is wrong in response. Please contact support. \n response: %(response)s", response=response)
                self.sudo().write({
                    "l10n_in_gstr1_blocking_level": "error",
                })
        elif response.get("error"):
            error_msg = ""
            error_codes = [e.get('code') for e in response["error"]]
            if 'no-credit' in error_codes:
                error_msg = self.env["account.move"]._l10n_in_edi_get_iap_buy_credits_message()
            else:
                error_msg = "<br/>".join(["[%s] %s" % (e.get("code"), html_escape(e.get("message"))) for e in response["error"]])
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": self._get_l10n_in_error_level(error_codes),
            })
        else:
            error_msg = _("Something is wrong in response. Please contact support")
            self.sudo().write({
                "l10n_in_gstr1_blocking_level": "error",
            })

        if self.l10n_in_gstr1_blocking_level:
            self.message_post(body=error_msg)

    def _cron_check_gstr1_status(self):
        sent_rtn = self.search([
            ("l10n_in_gstr1_status", "=", "waiting_for_status"),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
        ])
        for rtn in sent_rtn:
            rtn.check_l10n_in_gstr1_status()

    def _get_gst_doc_type_domain(self):
        base_domain = [
            ('name', 'not in', [False, '/', '']),
            ('posted_before', '=', True),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('state', 'in', ['posted', 'cancel']),
        ]
        return {
            '1': base_domain + [('move_type', '=', 'out_invoice'), ('debit_origin_id', "=", False)],
            '2': base_domain + [('move_type', '=', 'in_invoice'), ('l10n_in_is_self_invoice', '=', True)],
            '4': base_domain + [('move_type', '=', 'out_invoice'), ('debit_origin_id', "!=", False)],
            '5': base_domain + [('move_type', '=', 'out_refund')]
        }

    def _get_base_section_domain(self):
        return [
            ('company_id', 'in', (self.company_ids or self.company_id).ids),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('parent_state', '=', 'posted'),
        ]

    def _get_tax_detail_domain(self, is_iff_return=False):
        domain = self._get_base_section_domain()
        if is_iff_return:
            return list(Domain.AND([
                self._get_base_section_domain(),
                Domain('move_id.l10n_in_gstr_iff_exclude', '=', False),
            ])) + [('l10n_in_gstr_section', 'in', self._get_iff_section())]
        return (
            domain
            + [
                ('l10n_in_gstr_section', 'in', ['sale_b2b_rcm', 'sale_b2b_regular', 'sale_b2cl', 'sale_b2cs', 'sale_exp_wp', 'sale_exp_wop', 'sale_sez_wp', 'sale_sez_wop', 'sale_deemed_export', 'sale_cdnr_rcm',
                                                'sale_cdnr_regular', 'sale_cdnr_deemed_export', 'sale_cdnr_sez_wp', 'sale_cdnr_sez_wop', 'sale_cdnur_b2cl', 'sale_cdnur_exp_wp', 'sale_cdnur_exp_wop', 'sale_nil_rated',
                                                'sale_exempt', 'sale_non_gst_supplies']),
            ]
        )

    def action_generate_document_summary(self):
        if self.type_external_id != GSTR1_RETURN_TYPE:
            return False

        self.l10n_in_doc_summary_line_ids.unlink()
        Move = self.env['account.move']
        for doc_type, doc_domain in self._get_gst_doc_type_domain().items():
            grouped_data = self.env['account.move'].with_context(
                allowed_company_ids=(self.company_ids or self.company_id).ids
            )._read_group(
                domain=doc_domain,
                groupby=['sequence_prefix', 'state'],
                aggregates=['id:count', 'sequence_number:min', 'sequence_number:max', 'name:max'],
            )
            summary_map = {}
            for group in grouped_data:
                prefix, state, count, min_seq_number, max_seq_number, name = group
                format_string, format_values = Move._get_sequence_format_param(name)
                min_name = format_string.format(**{**format_values, 'seq': min_seq_number})
                max_name = format_string.format(**{**format_values, 'seq': max_seq_number})
                summary = summary_map.setdefault(prefix, {
                    'min_name': min_name,
                    'max_name': max_name,
                    'total_issued': 0,
                    'total_cancelled': 0
                })
                summary['min_name'] = min(summary['min_name'], min_name)
                summary['max_name'] = max(summary['max_name'], max_name)
                summary['total_issued'] += count
                if state == 'cancel':
                    summary['total_cancelled'] += count
            self.l10n_in_doc_summary_line_ids.create([
                {
                    'return_period_id': self.id,
                    'nature_of_document': doc_type,
                    'serial_from': values['min_name'],
                    'serial_to': values['max_name'],
                    'total_issued': values['total_issued'],
                    'total_cancelled': values['total_cancelled'],
                }
                for prefix, values in summary_map.items()
            ])
        return self.action_open_document_summary()

    def action_open_document_summary(self):
        context = {'default_return_period_id': self.id}
        if self.l10n_in_gstr1_status == 'filed':
            context.update({
                'create': False, 'edit': False, 'delete': False
            })
        return {
            'name': _("GSTR Document Summary"),
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_in.gstr.document.summary.line',
            'views': [(False, 'list')],
            'context': context,
            'domain': [('return_period_id', '=', self.id)],
        }

    def button_gstr1_filed(self):
        if self.l10n_in_gstr1_status != "sent":
            raise UserError(_("Before set as Filed, Status of GSTR-1 must be send"))
        self.write({
            'state': 'filed',
            'is_completed': True
        })

    # ===============================
    # GSTR-2B
    # ===============================

    def action_get_gstr2b_view_reconciled_invoice(self):
        self.ensure_one()
        domain = [("l10n_in_account_return_id", "=", self.id)]
        return {
            "name": _("Reconciled Bill"),
            "res_model": "account.move",
            "type": "ir.actions.act_window",
            'context': {'create': False, "search_default_l10n_in_gstr2b_status": True},
            "domain": domain,
            "view_mode": "list,form",
        }

    def action_get_l10n_in_gstr2b_data(self):
        self._l10n_in_check_config()
        self.sudo().write({
            "state": "fetching",
            "l10n_in_gstr2b_blocking_level": False,
        })
        self.env.ref('l10n_in_reports.ir_cron_auto_sync_gstr2b_data')._trigger()

    def get_l10n_in_gstr2b_data(self):
        if not self.company_id._is_l10n_in_gstr_token_valid():
            self.sudo().write({
                "l10n_in_gstr2b_blocking_level": "error",
                "state": "error_in_fetching"
            })
            msg = _("GSTR-2B data fetching failed: GST token expired or missing, Please regenerate it by verifying GST OTP.")
            self.message_post(body=msg)
            return
        response = self._l10n_in_get_gstr2b_data_request(company=self.company_id, month_year=self.l10n_in_month_year)
        if response.get("data"):
            gstr2b_data = response["data"]
            attachment_ids = self.env['ir.attachment'].create({
                'name': 'gstr2b_0.json',
                'mimetype': 'application/json',
                'raw': json.dumps(response).encode(),
            })
            if gstr2b_data.get("data", {}).get('fc'):
                number_of_files = gstr2b_data.get("data", {}).get('fc') + 1
                for file_num in range(1, number_of_files):
                    sub_response = self._l10n_in_get_gstr2b_data_request(company=self.company_id, month_year=self.l10n_in_month_year, file_number=file_num)
                    if not sub_response.get('error'):
                        attachment_ids += self.env['ir.attachment'].create({
                            'name': 'gstr2b_%s.json' % (file_num),
                            'mimetype': 'application/json',
                            'raw': json.dumps(sub_response).encode(),
                        })
                    else:
                        response = sub_response
            self.sudo().l10n_in_gstr2b_json_ids = attachment_ids
        if response.get('error'):
            error_msg = ""
            error_codes = [e.get('code') for e in response["error"]]
            if 'no-credit' in error_codes:
                error_msg = self.env["account.move"]._l10n_in_edi_get_iap_buy_credits_message()
            else:
                error_msg = "<br/>".join(["[%s] %s" % (e.get("code"), html_escape(e.get("message"))) for e in response["error"]])
            self.sudo().write({
                "l10n_in_gstr2b_blocking_level": self._get_l10n_in_error_level(error_codes),
                "state": "error_in_fetching"
            })
            self.message_post(body=error_msg)
        else:
            self.write({
                'state': 'fetch'
            })

    def _cron_get_gstr2b_data(self):
        for return_period in self.search([
            ('l10n_in_gstr2b_status', '=', 'fetching'),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
            ('l10n_in_gstr2b_blocking_level', '!=', 'error'),
        ]):
            return_period.get_l10n_in_gstr2b_data()

    def _l10n_in_convert_to_date(self, date):
        # can't use field.date.to_date because formate is different then DEFAULT_SERVER_DATE_FORMAT
        return datetime.strptime(date, "%d-%m-%Y").date()

    def _cron_gstr2b_match_data(self):
        return_periods = self.search([
            ('l10n_in_gstr2b_status', '=', 'fetch'),
            ('company_id.l10n_in_gst_efiling_feature', '=', True),
            ('l10n_in_gstr2b_blocking_level', '!=', 'error'),
        ])
        for return_period in return_periods:
            return_period.gstr2b_match_data()

    def gstr2b_match_data(self):
        """
            Matching GSTR-2B data with vendeors bills that bill date is in those return period
            and first match with the reference number and if reference number is match then try
            to match with invoice value, total amount and date of bill,
            if multipls reference found then add exceptions with that bill name,
            if there is no reference number found then metch with invoice value, total amount and date of bill
            and exceptions for reference number.
        """
        def _create_attachment(move, json_data, ref=None):
            return self.env['ir.attachment'].create({
                "name": "gstr2b_matching_data_%s.json" % (ref or move.ref),
                "raw": json.dumps(json_data).encode(),
                "res_model": "account.move" if move else False,
                "res_id": move.id if move else False,
                "mimetype": "application/json",
                })

        def _remove_special_characters(ref):
            """Remove special characters from bill reference numbers."""
            if not ref:
                return ref
            pattern = re.compile(r'[^a-zA-Z0-9]')
            return pattern.sub('', ref)

        def _get_tolerance_amount():
            return self.env['ir.config_parameter'].sudo().get_float(
                'l10n_in_reports.gstr2b_matching_tolerance_amount',
            ) or TOLERANCE_AMOUNT

        def remove_matched_bill_value(matching_dict, matching_keys_to_remove, matched_bill):
            for key in matching_keys_to_remove:
                # only remove matched bill
                if key in matching_dict:
                    matching_dict[key] -= matched_bill
                    # no value then delete key
                    if not matching_dict[key]:
                        del matching_dict[key]

        def match_bills(gstr2b_streamline_bills, matching_dict):
            create_vals = []
            checked_bills = self.env['account.move']
            tolerance_amount = _get_tolerance_amount()
            for gstr2b_bill in gstr2b_streamline_bills:
                bill_type = gstr2b_bill.get('bill_type')
                bill_date = gstr2b_bill.get('bill_date')
                bill_number = gstr2b_bill.get('bill_number')
                bill_vat = gstr2b_bill.get('vat')
                matching_keys = bill_irn = gstr2b_bill.get('irn')
                sanitized_ref = _remove_special_characters(bill_number)
                matched_bills = False
                # check the bill with IRN number first to reduce the unnecessary key generation
                matched_bills = matching_dict.get(bill_irn)
                if not matched_bills:
                    matching_keys = _get_matching_keys(
                        sanitized_ref, bill_vat, bill_date,
                        bill_type, gstr2b_bill.get('bill_total') or gstr2b_bill.get('bill_taxable_value'), bill_irn)
                    for matching_key in matching_keys:
                        if not matched_bills and matching_dict.get(matching_key):
                            matched_bills = matching_dict.get(matching_key)
                            break
                if matched_bills:
                    created_from_reconciliation = matched_bills.filtered(lambda b:
                        b.l10n_in_gstr2b_reconciliation_status == 'gstr2_bills_not_in_odoo' and b.state == 'draft')
                    checked_bills += created_from_reconciliation
                    matched_bills = matched_bills - created_from_reconciliation
                    if len(matched_bills) == 1:
                        remove_matched_bill_value(matching_dict, matching_keys, matched_bills)
                        exception = []
                        is_irn_matched = matched_bills.l10n_in_irn_number == bill_irn
                        sign = 1 if matched_bills.is_inbound(include_receipts=True) else -1
                        amount_total = matched_bills.amount_total_signed * sign
                        amount_untaxed = matched_bills.amount_untaxed_signed * sign
                        if is_irn_matched and matched_bills.state == 'draft':
                            exception.append(_("The IRN number is matching with GSTR-2B, but the bill is not validated yet."))
                        elif matched_bills.ref == bill_number or is_irn_matched:
                            if 'bill_taxable_value' in gstr2b_bill and gstr2b_bill['bill_taxable_value'] != matched_bills.amount_untaxed:
                                exception.append(_("Total Taxable amount as per GSTR-2B is %s", gstr2b_bill['bill_taxable_value']))
                            for line in matched_bills.line_ids:
                                if line.tax_line_id.amount < 0:
                                    amount_total += line.balance * sign
                            if (bill_pos := gstr2b_bill.get('bill_pos')) and bill_pos != matched_bills.l10n_in_state_id.l10n_in_tin:
                                place_of_supply = self.env['res.country.state'].search([('l10n_in_tin', '=', bill_pos)], limit=1)
                                exception.append(_("The place of supply as GSTR-2B is %s", place_of_supply.name))
                            if (
                                'bill_total' in gstr2b_bill
                                and not (amount_total - tolerance_amount <= gstr2b_bill['bill_total'] <= amount_total + tolerance_amount)
                            ):
                                exception.append(_("The total amount as per GSTR-2B is %s", gstr2b_bill['bill_total']))
                            if bill_vat and bill_vat != matched_bills.partner_id.vat:
                                exception.append(_("The GSTIN as per GSTR-2B is %s", bill_vat))
                            if bill_date and bill_date != matched_bills.invoice_date:
                                exception.append(_("The bill date as per GSTR-2B is %s", bill_date))
                            if (
                                matched_bills.move_type == 'in_refund' and bill_type == 'bill'
                                or matched_bills.move_type != 'in_refund' and bill_type == 'credit_note'
                            ):
                                invoice_type = 'Credit Note' if bill_type == 'credit_note' else 'Bill'
                                exception.append(_("The bill type as per GSTR-2B is %s", invoice_type))
                        elif (
                            (
                                gstr2b_bill.get('bill_total') == amount_total
                                or gstr2b_bill.get('bill_taxable_value') == amount_untaxed
                            )
                            and gstr2b_bill.get('vat') == matched_bills.partner_id.vat
                            and gstr2b_bill.get('bill_date') == matched_bills.invoice_date
                            and gstr2b_bill.get('bill_type') == ('credit_note' if matched_bills.move_type == 'in_refund' else 'bill')
                        ):
                            exception.append(_("The reference number as per GSTR-2B is %s", bill_number))
                        if exception and matched_bills.l10n_in_gstr2b_reconciliation_status == "manually_matched":
                            checked_bills += matched_bills
                            continue
                        matched_bills.write({
                            "l10n_in_exception": '<br/>'.join(exception),
                            "l10n_in_gstr2b_reconciliation_status": exception and "partially_matched" or "matched",
                            "l10n_in_account_return_id": self.id,
                        })
                        checked_bills += matched_bills
                        _create_attachment(matched_bills, gstr2b_bill.get('bill_value_json'))
                    else:
                        for bill in matched_bills:
                            _create_attachment(bill, gstr2b_bill.get('bill_value_json'))
                            other_bills = Markup("<br/>").join(Markup("<a href='#' data-oe-model='account.move' data-oe-id='%s'>%s</a>") % (
                                    other_bill.id, other_bill.name) for other_bill in matched_bills - bill)
                            bill.message_post(
                                subject=_("GSTR-2B Reconciliation"),
                                body=_(
                                    "The reference number is the same as on other bills: %(other_bills)s",
                                    other_bills=other_bills
                                )
                            )
                        matched_bills.write({
                            "l10n_in_exception": _("We have found the same reference in other bills. For more details, please check the message in Chatter."),
                            'l10n_in_gstr2b_reconciliation_status': "bills_not_in_gstr2",
                            "l10n_in_account_return_id": self.id,
                        })
                        checked_bills += matched_bills
                else:
                    partner = bill_vat and self.env['res.partner'].search([
                        *self.env['res.partner']._check_company_domain(self.company_id),
                        ('vat', '=', bill_vat),
                    ], limit=1)
                    journal = self.env['account.journal'].search([
                        *self.env['account.journal']._check_company_domain(self.company_ids or self.company_id),
                        ('type', '=', 'purchase')
                    ], order="sequence, id", limit=1)
                    if not partner or partner.l10n_in_gst_treatment not in ('deemed_export', 'uin_holders'):
                        l10n_in_gst_treatment = {
                            'impg': 'overseas',
                            'impgsez': 'special_economic_zone',
                        }.get(gstr2b_bill.get('section_code'), 'regular')
                    else:
                        l10n_in_gst_treatment = partner.l10n_in_gst_treatment
                    create_vals.append({
                        "move_type": bill_type == 'credit_note' and "in_refund" or "in_invoice",
                        "ref": bill_number,
                        "invoice_date": bill_date,
                        "partner_id": partner and partner.id or False,
                        "l10n_in_gst_treatment": l10n_in_gst_treatment,
                        "journal_id": journal.id,
                        "l10n_in_gstr2b_reconciliation_status": "gstr2_bills_not_in_odoo",
                        "review_state": 'todo',
                        "l10n_in_account_return_id": self.id,
                        "l10n_in_irn_number": bill_irn,
                        "message_ids": [(0, 0, {
                            'model': 'account.move',
                            'body': _(
                                "This bill was created from the GSTR-2B reconciliation because "
                                "no existing bill matched with the given details."
                            ),
                            'attachment_ids': _create_attachment(
                                self.env['account.move'],
                                gstr2b_bill.get('bill_value_json'),
                                ref=bill_number
                            ).ids
                        })]
                    })
            if create_vals:
                created_move = self.env['account.move'].create(create_vals)
                checked_bills += created_move
                self.env.cr.execute(SQL("""
                    UPDATE ir_attachment
                    SET res_id = msg.res_id,
                        res_model = 'account.move'
                    FROM ir_attachment att
                    JOIN message_attachment_rel rel ON rel.attachment_id = att.id
                    JOIN mail_message msg ON msg.id = rel.message_id
                    WHERE att.id = ir_attachment.id
                        AND att.res_model IS NULL
                        AND att.res_id = 0
                        AND msg.model = 'account.move'
                        AND msg.res_id IN %(ids)s
                """, ids=tuple(created_move.ids)))
            return checked_bills

        def _get_matching_keys(ref, vat, invoice_date, invoice_type, amount, irn):
            # remove space from ref
            ref = ref and ref.replace(" ", "")
            key_combinations = [
                (irn,),
                (ref, vat, invoice_type, invoice_date, amount),  # Best case if no irn
                (ref, vat, invoice_type, invoice_date),
                (ref, vat, invoice_type, amount),
                (ref, vat, invoice_type),

                (ref, vat, invoice_date, amount),
                (ref, vat, invoice_date),
                (ref, vat, amount),
                (ref, vat),

                (ref, invoice_type, invoice_date, amount),
                (ref, invoice_type, invoice_date),
                (ref, invoice_type, amount),
                (ref, invoice_type),

                (ref, invoice_date, amount),
                (ref, invoice_date),
                (ref, amount),
                (ref,),
                (vat, invoice_type, invoice_date, amount)  # Worst case
            ]

            # Filter out false keys from key combinations
            filtered_keys = [key for key in key_combinations if any(key)]
            # Convert tuple keys to string keys
            formatted_keys = ["-".join(map(str, key)) for key in filtered_keys]
            return formatted_keys

        def _get_all_bill_by_matching_key(gstr2b_late_streamline_bills):
            AccountMove = self.env["account.move"]
            matching_dict = {}
            domain = ['|',
                ("l10n_in_account_return_id", "=", self.id),
                '&', ("move_type", "in", AccountMove.get_purchase_types()),
                '&', ("invoice_date", ">=", self.date_from),
                '&', ("invoice_date", "<=", self.date_to),
                '&', ("company_id", "in", self.company_ids.ids or self.company_id.ids),
                '|',
                    '&', ("state", "=", "posted"),
                         ("l10n_in_gst_treatment", "not in", ('composition', 'unregistered', 'consumer')),
                    '&', ("state", "in", ["draft", "cancel"]),
                        ("l10n_in_irn_number", "!=", False),
            ]
            to_match_bills = AccountMove.search(domain)
            for late_bill in gstr2b_late_streamline_bills:
                bill_month_start, bill_month_end = date_utils.get_month(late_bill.get('bill_date'))
                late_bill_domain = [
                    ('l10n_in_account_return_id', '!=', self.id),
                    ("invoice_date", ">=", bill_month_start),
                    ("invoice_date", "<=", bill_month_end),
                    ("company_id", "in", self.company_ids.ids or self.company_id.ids),
                    ("move_type", "in", AccountMove.get_purchase_types()),
                    "|",
                        ("state", "in", ["draft", "cancel"]),
                        '&', '&', ("state", "=", "posted"),
                            ("l10n_in_gstr2b_reconciliation_status", "not in", ('matched', 'partially_matched', 'manually_matched')),
                            ("l10n_in_gst_treatment", "not in", ('composition', 'unregistered', 'consumer')),
                ]
                if late_bill.get('irn'):
                    late_bill_domain += [
                        "|", ("ref", "=", late_bill.get('bill_number')),
                            ("l10n_in_irn_number", "=", late_bill['irn']),
                    ]
                else:
                    late_bill_domain += [("ref", "=", late_bill.get('bill_number'))]
                to_match_bills += AccountMove.search(late_bill_domain)
            filtered_to_match_bills = AccountMove
            for bill in to_match_bills:
                # There is no tax mins bill from unregistered and consumer so no need to match
                # If set this in domain then it will impact the performance because of tax_ids is m2m field, so put this condition here
                if bill.state == 'posted' and not bill.line_ids.tax_ids:
                    continue
                bill_type = 'bill'
                amount = bill.amount_total
                # For SEZ and overseas amount get from Goverment is amount_untaxed
                if bill.l10n_in_gst_treatment in ('special_economic_zone', 'overseas'):
                    amount = bill.amount_untaxed
                if bill.move_type == 'in_refund':
                    bill_type = 'credit_note'
                # Sanitize the reference to remove any special characters, ensuring it is suitable for matching
                sanitized_ref = _remove_special_characters(bill.ref)
                # Retrieve matching keys based on the sanitized reference, partner VAT, invoice date, bill type, and amount
                matching_keys = _get_matching_keys(sanitized_ref, bill.partner_id.vat, bill.invoice_date, bill_type, amount, bill.l10n_in_irn_number)
                for matching_key in matching_keys:
                    matching_dict.setdefault(matching_key, AccountMove)
                    matching_dict[matching_key] += bill
                filtered_to_match_bills += bill
            return filtered_to_match_bills, matching_dict

        def get_streamline_bills_from_json(json_payload):
            vals_list = []
            late_vals_list = []
            gstr2b_bills = json_payload.get("data", {}).get('data', {}).get("docdata", {})
            for section_code, bill_datas in gstr2b_bills.items():
                if section_code in ('b2b', 'cdnr'):
                    for bill_by_vat in bill_datas:
                        key = section_code == 'cdnr' and 'nt' or 'inv'
                        for doc_data in bill_by_vat.get(key):
                            bill_date = self._l10n_in_convert_to_date(doc_data.get('dt'))
                            vals = {
                                'vat': bill_by_vat.get('ctin'),
                                'bill_number': section_code == 'cdnr' and doc_data.get('ntnum') or doc_data.get('inum'),
                                'bill_date': bill_date,
                                'bill_total': doc_data.get('val'),
                                'bill_value_json': doc_data,
                                'bill_type': section_code == 'cdnr' and doc_data.get('typ') == 'C' and 'credit_note' or 'bill',
                                'section_code': section_code,
                                "bill_pos": doc_data.get('pos'),
                                'irn': doc_data.get('irn') and doc_data.get('irn').lower() or False,
                            }
                            vals_list.append(vals)
                            if bill_date < self.date_from:
                                late_vals_list.append(vals)
                if section_code == 'impg':
                    for bill_data in bill_datas:
                        vals_list.append({
                            'vat': False,
                            'bill_number': bill_data.get('boenum'),
                            'bill_date': self._l10n_in_convert_to_date(bill_data.get('boedt')),
                            'bill_taxable_value': bill_data.get('txval'),
                            'bill_value_json': bill_data,
                            'bill_type': 'bill',
                            'section_code': section_code,
                        })
                if section_code == 'impgsez':
                    for bill_by_vat in bill_datas:
                        for bill_data in bill_by_vat.get('boe'):
                            vals_list.append({
                                'vat': bill_by_vat.get('ctin'),
                                'bill_number': bill_data.get('boenum'),
                                'bill_date': self._l10n_in_convert_to_date(bill_data.get('boedt')),
                                'bill_taxable_value': bill_data.get('txval'),
                                'bill_value_json': bill_data,
                                'bill_type': 'bill',
                                'section_code': section_code,
                            })
            return vals_list, late_vals_list

        def process_json(json_dump_list):
            gstr2b_streamline_bills = []
            gstr2b_late_streamline_bills = []
            for json_dump in json_dump_list:
                json_payload = json.loads(json_dump)
                vals_list, late_vals_list = get_streamline_bills_from_json(json_payload)
                gstr2b_streamline_bills += vals_list
                gstr2b_late_streamline_bills += late_vals_list
            to_match_bills, matching_dict = _get_all_bill_by_matching_key(gstr2b_late_streamline_bills)
            checked_invoice = match_bills(gstr2b_streamline_bills, matching_dict)
            self.sudo().state = len(to_match_bills) == len(
                checked_invoice.filtered(lambda l: l.l10n_in_gstr2b_reconciliation_status in ('matched'))
            ) and 'matched' or 'partially_matched'
            invoice_not_in_gstr2b = (to_match_bills - checked_invoice)
            invoice_not_in_gstr2b.write({
                'l10n_in_gstr2b_reconciliation_status': "bills_not_in_gstr2",
                'l10n_in_exception': "Not Available in GSTR2B",
                "l10n_in_account_return_id": self.id,
            })

        json_payload_list = [
            json_file.raw.content
            for json_file in self.sudo().l10n_in_gstr2b_json_ids
            if json_file.mimetype == 'application/json' and json_file.raw.content
        ]
        if json_payload_list:
            process_json(json_payload_list)
        else:
            self.sudo().write({
                "l10n_in_gstr2b_blocking_level": "error",
                "state": "error_in_fetching",
            })
            msg = _("Somehow, the attached GSTR2B file is not in JSON format.")
            self.message_post(body=msg)

    def button_gstr2b_completed(self):
        if not self.l10n_in_gstr2b_status in ('matched', 'partially_matched'):
            raise UserError(_("Status of GSTR-2B must be fully matched or partially matched"))
        if not self.is_completed:
            self.write({
                'state': 'completed',
                'is_completed': True
            })

    # ===============================
    # Bills from E-Invoice IRN
    # ===============================

    def action_l10n_in_get_irn_data(self):
        """
        Fetch the IRN (Invoice Reference Number) data for the company.
        Ensures the company is in production and has IAP credits, then triggers a cron to fetch
        the list of IRNs relevant to the current GST period.

        :returns: a notification action informing the user that the fetch is in progress.
        """
        if self.company_id.sudo().l10n_in_edi_production_env:
            edi_credits = self.env["iap.account"].get_credits(service_name="l10n_in_edi")
            if edi_credits < 3:
                self.l10n_in_irn_status = 'process_with_error'
                self.message_post(
                    body=self.env['account.move']._l10n_in_edi_get_iap_buy_credits_message()
                )
                return True
        self._l10n_in_check_config()
        self.l10n_in_irn_status = 'to_download'
        self.message_post(body=_("IRN Processing is running in the background."))
        self.env.ref('l10n_in_reports.ir_cron_auto_sync_einvoice_irn')._trigger()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'sticky': False,
                'message': _("Processing is running in the background. You can continue your work."),
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'soft_reload',
                },
            }
        }

    def _get_l10n_in_irn_data(self):
        """ Fetch and process IRN data
        The process of retrieving IRN data entails the following steps:
        1. Obtain an e-invoice file token from the IAP.
        2. Use the token to retrieve the e-invoice file details, these include encryption keys and file URLs.
        3. Retrieve the IRN list file data from the encrypted file URLs, creates JSON attachments for each file. In most cases there is only one.
        4. Update the IRN status and trigger the next step in the workflow if successful.
        """
        def extract_token_from_error(response):
            """
            Extracts a file token from a specific error message if the error code matches.
            Handles specific errors and performs appropriate actions.
            :param response: The JSON response containing error details.
            :returns:
                - The extracted token as a string if `EINV30130` is found.
                - A dictionary with `error_code` if `EINV30109` is found (indicates retry).
                - `False` if no relevant error is found.
            """
            errors = response.get('error', [])
            if isinstance(errors, dict):
                errors['code'] = errors.pop('error_cd', None)
            for error in list(errors):
                error_code = error.get('code', '')
                # Handle `EINV30130`: Extract file token from the error message
                if error_code == 'EINV30130':
                    token_match = re.search(r'token\s([a-f0-9]+)(?=.*The link is valid till 1 day)', error.get('message', ''))
                    if token_match:
                        return token_match.group(1)
                # Handle `EINV30109`: File generation in progress, schedule a retry
                elif error_code == 'EINV30109':
                    # Dynamically activate and schedule a retry for the cron job after 10 minutes
                    self.env.ref("l10n_in_reports.ir_cron_auto_sync_einvoice_irn")._trigger(
                        fields.Datetime.now() + timedelta(minutes=10)
                    )
                    self.message_post(body=_("File generation is in progress on the GST portal. Auto retry in 10 minutes."))
                    return 'EINV30109_file_under_process'
            return False

        # Retrieve file token
        file_token_response = self._l10n_in_get_einvoice_file_token_request(
            company=self.company_id,
            month_year=self.l10n_in_month_year,
            section_code="B2B",
        )
        if (file_token := file_token_response.get('data', {}).get('token')) is None:
            file_token = extract_token_from_error(file_token_response)
        if file_token == 'EINV30109_file_under_process':
            return False
        if not file_token:
            raise IrnException(file_token_response.get('error', {}))
        # Retrieve encryption keys and URLs for the e-invoice files
        einvoice_details_response = self._l10n_in_get_einvoice_details_from_file_request(
            company=self.company_id,
            month_year=self.l10n_in_month_year,
            token=file_token,
        )
        if not (
            (data := einvoice_details_response.get('data', {}))
            and (url_list := [url['ul'] for url in data.get('urls') if 'ul' in url])
            and (key := data.get('ek'))
        ):
            raise IrnException(einvoice_details_response.get('error', {}))
        # Process the URLs to fetch IRN data and create attachments, exluding those that already exist
        attachment_ids = self.env['ir.attachment']
        for url in url_list:
            irn_details_response = self._l10n_in_gstr_encrypted_large_file_data_request(
                company=self.company_id,
                month_year=self.l10n_in_month_year,
                url=url,
                encryption_key=key,
            )
            data = irn_details_response.get('data', {})
            if not data or not data.get('irnList', {}):
                raise IrnException(irn_details_response.get('error', {}))
            attachment_ids |= self.env['ir.attachment'].create({
                'name': f'file_{url}.json',
                'mimetype': 'application/json',
                'raw': json.dumps(data).encode(),
            })
        if attachment_ids:
            self.l10n_in_irn_json_attachment_ids.unlink()
            self.l10n_in_irn_json_attachment_ids = attachment_ids
        # Update the IRN status and trigger the next workflow step
        self.l10n_in_irn_status = "to_process"
        self.env.ref('l10n_in_reports.ir_cron_auto_match_einvoice_irn')._trigger()

    def l10n_in_irn_match_data(self):
        """
        Matches or creates bills (account moves) based on IRN (Invoice Reference Number) data retrieved from JSON attachments.

        This method processes JSON data containing IRN information and attempts to match each entry with existing bills in the system.
        If a match is found, the IRN number is updated. If no match is found, a new bill is created.
        It handles updates, cancellations, and posting relevant messages based on the IRN status.
        """
        AccountMove = self.env['account.move']
        checked_moves = self.env['account.move']
        # Collect JSON data from the attachments
        json_payload_list = [
            json_file.raw.content
            for json_file in self.l10n_in_irn_json_attachment_ids
                if json_file.mimetype == 'application/json'
        ]

        if not json_payload_list:
            # No valid JSON attachments found, log an error
            self.l10n_in_irn_status = "process_with_error"
            msg = _("Somehow this IRN attachment is not JSON. Please attempt to retrieve the data from the portal again.")
            self.message_post(body=msg)
            return checked_moves

        # Process the JSON data
        irn_numbers = set()
        streamline_bills = []
        for json_dump in json_payload_list:
            json_payload = json.loads(json_dump)
            for entry in json_payload.get('irnList', {}):
                ctin = entry.get('ctin')
                irn_details = entry.get('irnDtl', [])
                for detail in irn_details:
                    vals = {
                        'vat': ctin,
                        'bill_number': detail.get('docNum'),
                        'bill_date': datetime.strptime(detail.get('docDt'), '%d/%m/%Y').strftime('%Y-%m-%d'),
                        'bill_total': detail.get('totInvAmt'),
                        'bill_value_json': detail,
                        'bill_type': detail.get('docType'),
                        'section_code': detail.get('supplyType'),
                        'irn_number': detail.get('irn'),
                        'l10n_in_irn_status': detail.get('irnStatus'),
                        'ack_no': detail.get('ackNo'),
                        'ack_date': detail.get('ackDt'),
                        'ewb_no': detail.get('ewbNo'),
                        'ewb_date': detail.get('ewbDt'),
                        'cancel_date': detail.get('cnldt')
                    }
                    streamline_bills.append(vals)
                    irn_numbers.add(detail.get('irn'))

        # Perform bulk search for bills with matching IRN numbers
        existing_bills = AccountMove.search([
            ("move_type", "in", AccountMove.get_purchase_types()),
            ("l10n_in_irn_number", "in", list(irn_numbers)),
            ("company_id", "in", self.company_ids.ids or self.company_id.ids),
        ])
        # Create a mapping of existing bills by IRN number
        existing_bills_dict = {bill.l10n_in_irn_number: bill for bill in existing_bills}

        # Match or create bills based on the extracted data
        for bill in streamline_bills:
            irn_number = bill.get('irn_number')
            bill_already_exists = existing_bills_dict.get(irn_number)
            if not bill_already_exists:
                # Check if the bill exists by bill number and date if IRN number does not match
                domain = [
                    ("move_type", "in", AccountMove.get_purchase_types()),
                    ("ref", "=", bill.get('bill_number')),
                    ("invoice_date", "=", bill.get('bill_date')),
                    ("company_id", "in", self.company_ids.ids or self.company_id.ids),
                ]
                if bill.get('vat'):
                    domain.append(("partner_id.vat", "=", bill.get('vat')))
                bill_already_exists = AccountMove.search(domain, limit=1)

                if bill_already_exists:
                    # Update the existing bill with the IRN number
                    bill_already_exists.l10n_in_irn_number = irn_number
                    msg = _("This bill was found in the GST portal while retrieving the list of IRNs.")
                    bill_already_exists.message_post(body=msg)

            if not bill_already_exists:
                # Create a new bill if no match is found
                journal = self.env['account.journal'].search([
                    *self.env['account.journal']._check_company_domain(self.company_ids or self.company_id),
                    ('type', '=', 'purchase')
                ], order="sequence, id", limit=1)
                move_type = "in_invoice" if bill.get('bill_type') != "CRN" else "in_refund"
                created_move = self.env['account.move'].with_context(skip_is_manually_modified=True).create({
                    'journal_id': journal.id,
                    'move_type': move_type,
                    'l10n_in_irn_number': irn_number,
                    'invoice_date': bill.get('bill_date'),
                    'ref': bill.get('bill_number')
                })

                if self.l10n_in_gstr_activate_einvoice_fetch == 'automatic':
                    try:
                        gov_json_data = created_move._l10n_in_retrieve_details_from_irn(irn_number, self.company_id)
                    except IrnException as e:
                        if str(e) == 'no-credit':
                            message = self.env['account.move']._l10n_in_edi_get_iap_buy_credits_message()
                        else:
                            message = str(e)
                        created_move.message_post(body=Markup("%s<br/> %s") % (_("Fetching IRN details failed with error(s):"), message))
                        checked_moves |= created_move
                        continue
                    if gov_json_data:
                        # Create an attachment for the fetched data and update the bill
                        attachment = self.env['ir.attachment'].create({
                            # Limit the name to 45 characters to avoid exceeding the limit on e-invoice portal
                            'name': f'{irn_number[:45]}.json',
                            'mimetype': 'application/json',
                            'raw': json.dumps(gov_json_data).encode(),
                            'res_model': 'account.move',
                            'res_id': created_move.id,
                        })
                        msg = _("This bill was created from the GST portal because no existing invoice matched the provided details.")
                        created_move.message_post(body=msg)
                        created_move._extend_with_attachments(created_move._to_files_data(attachment), new=True)

                        # Cancel the created bill if the IRN status indicates cancellation
                        if bill.get('l10n_in_irn_status') == 'CNL' and created_move.state != 'cancel':
                            created_move.message_post(body=_("This bill has been marked as canceled based on the e-invoice status."))
                            created_move.button_cancel()
            else:
                # Cancel the existing bill if the IRN status indicates cancellation
                if bill.get('l10n_in_irn_status') == 'CNL' and bill_already_exists.state != 'cancel':
                    bill_already_exists.message_post(
                        body=_("This bill has been marked as canceled based on the e-invoice status.")
                    )
                    bill_already_exists.button_cancel()

            checked_moves |= bill_already_exists or created_move

        # Post a final message with the number of processed bills
        msg = _("Fetching complete. %s bills have been matched or created.", len(checked_moves))
        self.message_post(body=msg)
        self.l10n_in_irn_fetch_date = fields.Date.context_today(self)
        self.l10n_in_irn_status = False  # Reset IRN status after processing

    def _cron_get_irn_data(self):
        """
        Cron job to fetch IRN data for GST return periods with 'to_download' status.
        Calls `_get_l10n_in_irn_data()` for each period, handling errors if they occur.

        :rtype: None
        """
        return_periods = self.search([
            ('l10n_in_irn_status', '=', 'to_download'),
            ('company_id.l10n_in_fetch_vendor_edi_feature', '=', True),
        ])
        for return_period in return_periods:
            try:
                return_period._get_l10n_in_irn_data()
            except IrnException as e:
                return_period.l10n_in_irn_status = 'process_with_error'
                if str(e) == 'no-credit':
                    message = self.env['account.move']._l10n_in_edi_get_iap_buy_credits_message()
                else:
                    message = str(e)
                return_period.message_post(body=Markup("%s<br/> %s") % (_("Fetching List of e-invoice..."), message))

    def _cron_irn_match_data(self):
        """
        Cron job method that matches IRN data for GST return periods with 'to_process' status.

        This method searches for all GST return periods marked for IRN data processing and
        calls the `l10n_in_irn_match_data` method on each applicable return period to perform the matching operation.

        :rtype: None
        """
        return_periods = self.search([
            ('l10n_in_irn_status', '=', 'to_process'),
            ('company_id.l10n_in_fetch_vendor_edi_feature', '=', True),
        ])
        for return_period in return_periods:
            return_period.l10n_in_irn_match_data()

    # ========================================
    # Checks and Actions
    # ========================================

    def action_reset_tax_return_common(self):
        """
        Reset the tax return to its initial state.
        - GSTR-1/IFF: resets the state and blocking level. helpful in case of error user can re-start the process.
        - IFF: unlinks the moves associated with the return and resets their status to False.
        - GSTR-2B: resets the state to 'fetch' or False state
        """
        _ = self.env._
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise UserError(_("Only an Accounting Administrator can reset a tax return"))

        if self.type_external_id in (GSTR1_RETURN_TYPE, GSTR_IFF_RETURN_TYPE):
            self._reset_checks_for_states([self.state, False])
            self.write({
                'state': False,
                'l10n_in_gstr1_blocking_level': False,
                'is_completed': False
            })
            if self.type_external_id == GSTR_IFF_RETURN_TYPE:
                excluded_moves = self._get_iff_excluded_moves()
                excluded_moves.l10n_in_gstr_iff_exclude = False

            self.sudo().message_post(body=_("Return has been reset to new state."))
            return True

        if self.type_external_id == GSTR2B_RETURN_TYPE:
            if self.is_completed:
                self._mark_uncompleted()

            # Reset state bubble to new for the case when state is new but it was marked as complete
            if not self.state or self.state == 'error_in_fetching':
                self._reset_checks_for_states([self.state])
                self.write({
                    'state': False,
                    'l10n_in_gstr2b_blocking_level': False,
                })
                self.sudo().message_post(body=_("GSTR-2B return has been reset to new state."))
            else:
                self._reset_checks_for_states([self.state, 'fetch'])
                self.write({
                    'state': 'fetch',
                    'l10n_in_gstr2b_blocking_level': False,
                })
                self.sudo().message_post(body=_("GSTR-2B return has been reset to fetch state."))
            return True
        return super().action_reset_tax_return_common()

    def _review_checks(self):
        self.refresh_checks()
        blocking_checks = self.check_ids.filtered(lambda check: check.result in ('todo', 'anomaly'))
        if blocking_checks:
            raise UserError(_("Some checks fail, please solve them before proceeding."))

    def _proceed_with_locking(self):
        """
        Override to handle the final steps of the locking process gstr1 return.
        following steps are performed:
        - run checks in the current stage
        - set the lock date to today
        - change state to 'reviewed' as it's last step in validation process
        """
        self.ensure_one()
        if self.type_external_id in GSTR_RETURN_TYPES:
            domain = [
                ('company_id', '=', self.company_id.id),
                ('type_id', '=', self.type_id.id),
                ('date_deadline', '<', self.date_deadline),
                ('date_lock', '=', False),
                ('is_completed', '=', False),
                ('return_type_category', '!=', 'audit'),
            ]
            count = self.env['account.return'].search_count(domain, limit=1)
            if count:
                raise UserError(_("You cannot lock this return as there are previous returns that are waiting to be posted."))
            self._review_checks()
            self.date_lock = fields.Date.context_today(self)
            self.state = 'reviewed'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'title': self.env._("Checks Validated"),
                    'message': self.env._("Checks have been validated successfully. You can now proceed to the next step."),
                    'next': {'type': 'ir.actions.act_window_close'},
                },
            }
        return super()._proceed_with_locking()

    def _run_checks(self, check_codes_to_ignore):
        if self.type_external_id == GSTR2B_RETURN_TYPE:
            return self._check_suite_in_gstr2b_report(check_codes_to_ignore)
        if self.type_external_id == CMP08_RETURN_TYPE:
            return self._check_suite_in_cmp08_report(check_codes_to_ignore)
        if self.type_external_id == GSTR4_RETURN_TYPE:
            return self._check_suite_in_gstr4_report(check_codes_to_ignore)

        if self.type_external_id not in (GSTR1_RETURN_TYPE, GSTR_IFF_RETURN_TYPE):
            return super()._run_checks(check_codes_to_ignore)

        check_codes_to_ignore.update([
            'check_bills_attachment',
            'check_draft_entries',
            'check_match_all_bank_entries',
            'check_tax_countries',
            'check_company_data',
            'check_vat_reconciliation',
        ])

        in_checks = self._check_suite_in_gstr1_report(check_codes_to_ignore)

        if self.type_external_id == GSTR_IFF_RETURN_TYPE:
            in_checks += self._check_suite_in_gstr_iff_report(check_codes_to_ignore)

        return super()._run_checks(check_codes_to_ignore) + in_checks

    def _get_iff_section(self):
        return [
            'sale_b2b_rcm',
            'sale_b2b_regular',
            'sale_deemed_export',
            'sale_sez_wp',
            'sale_sez_wop',
            'sale_cdnr_rcm',
            'sale_cdnr_regular',
            'sale_cdnr_deemed_export',
            'sale_cdnr_sez_wp',
            'sale_cdnr_sez_wop',
        ]

    def _get_l10n_in_reports_aml_domain(self):
        report = self.type_id.report_id
        options = self._get_closing_report_options()
        options_domain = report._get_options_domain(options, date_scope='strict_range')
        section_domain = [('l10n_in_gstr_section', '=like', 'sale%')]
        if self.type_external_id == GSTR_IFF_RETURN_TYPE:
            section_domain = [('l10n_in_gstr_section', 'in', self._get_iff_section())]
        aml_domain = Domain.AND([
                options_domain,
                [
                    *section_domain,
                    ('display_type', '=', 'product'),
                ]
            ])
        return aml_domain

    def _get_iff_submission_domain(self):
        self.ensure_one()
        return Domain.AND([
            self._get_base_section_domain(),
            [('l10n_in_gstr_section', 'in', self._get_iff_section())],
        ])

    def _get_iff_excluded_moves(self):
        self.ensure_one()
        aml_domain = Domain.AND([
            self._get_base_section_domain(),
            [
                ('move_id.l10n_in_gstr_iff_exclude', '=', True),
                ('l10n_in_gstr_section', 'in', self._get_iff_section()),
            ],
        ])
        return self.env['account.move.line'].search(aml_domain).move_id

    def _check_suite_in_gstr1_report(self, check_codes_to_ignore):
        """ common checks for GSTR-1 and GSTR-1 IFF """
        checks = []
        aml_domain = self._get_l10n_in_reports_aml_domain()
        options = self._get_closing_report_options()

        # Ignore the check's that are not applicable for GSTR-1 IFF
        if self.type_external_id == GSTR_IFF_RETURN_TYPE:
            check_codes_to_ignore.update(['missing_document_summary', 'unlinked_unregistered_inter_state_reversed_move'])

        # Invalid Intra-State Tax
        if 'invalid_intra_state_tax' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_intra_state_tax_on_lines(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'invalid_intra_state_tax',
                'name': _("Apply Appropriate Tax"),
                'message': _("IGST is not applicable for Intra State Transactions."),
                'records_model': self.env['ir.model']._get('account.move.line').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Invalid tax for Intra State Transaction"),
                    views=[(False, 'list')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Invalid Inter-State Tax
        if 'invalid_inter_state_tax' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_inter_state_tax_on_lines(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'invalid_inter_state_tax',
                'name': _("Wrong CGST/SGST on Inter-State Transactions"),
                'message': _("SGST and CGST are not applicable for Inter State Transactions."),
                'records_model': self.env['ir.model']._get('account.move.line').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Invalid tax for Inter State Transaction"),
                    views=[(False, 'list')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Missing HSN
        if 'missing_hsn_code' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_no_hsn_products(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'missing_hsn_code',
                'name': _("Missing HSN Codes"),
                'message': _("Certain Product Lines does not have HSN in Journal Items."),
                'records_model': self.env['ir.model']._get('account.move.line').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Missing HSN for Journal Items"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        # Invalue UQC code
        if 'invalid_uqc_code' not in check_codes_to_ignore:
            _template, line_ids = self.env['l10n_in.report.handler']._get_invalid_uqc_codes(aml_domain)
            line_count = len(line_ids)
            checks.append({
                'code': 'invalid_uqc_code',
                'name': _("Invalid UQC Codes"),
                'message': _("UQC code must match the Indian GST standards."),
                'records_model': self.env['ir.model']._get('uom.uom').id,
                'records_count': line_count,
                'result': 'anomaly' if line_ids else 'reviewed',
                'action': line_ids._get_records_action(
                    name=_("Invalid UQC Code"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', line_ids.ids)]
                ) if line_ids else None,
            })

        if 'unlinked_unregistered_inter_state_reversed_move' not in check_codes_to_ignore:
            _template, move_ids = self.env['l10n_in.report.handler']._get_unlinked_unregistered_inter_state_reversed_moves(options)
            move_count = len(move_ids)
            checks.append({
                'code': 'unlinked_unregistered_inter_state_reversed_move',
                'name': _("Unlinked Unregistered Credit Notes"),
                'message': _("Credit Notes issued without reference to an invoice"),
                'records_model': self.env['ir.model']._get('account.move').id,
                'records_count': move_count,
                'result': 'anomaly' if move_ids else 'reviewed',
                'action': move_ids._get_records_action(name=_("Credit Notes")) if move_ids else None,
            })

        # Document Summary Check
        if 'missing_document_summary' not in check_codes_to_ignore:
            line_ids = self.l10n_in_doc_summary_line_ids.ids
            line_count = len(line_ids)
            checks.append({
                'code': 'missing_document_summary',
                'name': _("Missing Document Summary"),
                'message': _("Document Summary Lines are required for GSTR-1. Click to enter or verify the auto generated document summary lines."),
                'result': 'anomaly' if not line_count else 'reviewed',
                'action': self.action_open_document_summary(),
            })
        return checks

    def _check_suite_in_gstr2b_report(self, check_codes_to_ignore):
        checks = []
        if not self.l10n_in_fetch_vendor_edi_feature_enabled:
            check_codes_to_ignore.add('missing_fetch_einvoice')
            self.check_ids.filtered(lambda check: check.code == 'missing_fetch_einvoice').unlink()
        success_date = self.date_to + relativedelta(months=+1, day=2)
        if 'missing_fetch_einvoice' not in check_codes_to_ignore:
            checks.append({
                'code': 'missing_fetch_einvoice',
                'name': _("Fetch Vendor e-invoice"),
                'message': _("Fetch vendor e-Invoice data for this return period"),
                'result': 'reviewed' if self.l10n_in_irn_fetch_date and self.l10n_in_irn_fetch_date >= success_date else 'anomaly',
            })
        return checks

    def _check_suite_in_gstr_iff_report(self, check_codes_to_ignore):
        checks = []
        _ = self.env._
        aml_domain = self._get_iff_submission_domain()
        if 'iff_value_limit' not in check_codes_to_ignore:
            included_aml_domain = Domain.AND([aml_domain, [('move_id.l10n_in_gstr_iff_exclude', '=', False)]])
            move_ids = self.env['account.move.line'].search(included_aml_domain).move_id
            all_move_ids = self.env['account.move.line'].search(aml_domain).move_id
            total_value = sum(move_ids.mapped('amount_untaxed_signed'))
            inr_currency = self.env.ref('base.INR')
            checks.append({
                'code': 'iff_value_limit',
                'name': _("IFF Invoice Value Limit"),
                'message': _(
                    "The cumulative taxable value of records reported in IFF must not exceed "
                    "the prescribed limit of %(amount_limit)s. The current cumulative taxable value is %(value)s.",
                    amount_limit=formatLang(self.env, IFF_VALUE_LIMIT, currency_obj=inr_currency),
                    value=formatLang(self.env, total_value, currency_obj=inr_currency),
                ),
                'records_model': self.env['ir.model']._get('account.move').id,
                'result': 'anomaly' if total_value > IFF_VALUE_LIMIT else 'reviewed',
                'action': all_move_ids._get_records_action(
                    name=_("Invoices Reported in IFF"),
                    views=[(self.env.ref('l10n_in_reports.view_account_move_list_inherit_account').id, 'list'), (False, 'form')],
                    domain=[('line_ids', 'any', aml_domain)],
                    context={
                        'group_by': ['l10n_in_gstr_iff_exclude'],
                        'expand': True,
                    },
                )
            })
        return checks

    def _check_suite_in_cmp08_report(self, check_codes_to_ignore):
        checks = []
        options = self._get_closing_report_options()
        _ = self.env._

        if 'regular_tax_moves' not in check_codes_to_ignore:
            regular_tax_moves = self.env['account.move'].search(
                [
                    ('date', '>=', options['date']['date_from']),
                    ('date', '<=', options['date']['date_to']),
                    ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']),
                    ('state', '=', 'posted'),
                    ('line_ids.tax_line_id.l10n_in_tax_type', '=', 'gst'),
                ]
            )
            checks.append({
                'code': 'regular_tax_moves',
                'name': _("Apply Appropriate Sale Tax"),
                'message': _("Regular Tax Rate not applicable in sale for Composition scheme"),
                'result': 'anomaly' if regular_tax_moves else 'reviewed',
                'action': regular_tax_moves._get_records_action(
                    name=_("Invalid Moves"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', regular_tax_moves.ids)]
                ) if regular_tax_moves else None
            })

        if 'inter_state_transaction_moves' not in check_codes_to_ignore:
            inter_state_transaction_moves = self.env['account.move'].search(
                [
                    ('date', '>=', options['date']['date_from']),
                    ('date', '<=', options['date']['date_to']),
                    ('move_type', 'in', ['out_invoice', 'out_refund', 'out_receipt']),
                    ('state', '=', 'posted'),
                    ('l10n_in_transaction_type', '=', 'inter_state'),
                ]
            )
            checks.append({
                'code': 'inter_state_transaction_moves',
                'name': _("No Inter State Sale"),
                'message': _("Composition Dealers cannot make sales outside their home state"),
                'result': 'anomaly' if inter_state_transaction_moves else 'reviewed',
                'action': inter_state_transaction_moves._get_records_action(
                    name=_("Invalid Moves"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', inter_state_transaction_moves.ids)]
                ) if inter_state_transaction_moves else None
            })
        return checks

    def _check_suite_in_gstr4_report(self, check_codes_to_ignore):
        checks = []
        options = self._get_closing_report_options()
        _ = self.env._

        if 'cmp08_filed' not in check_codes_to_ignore:
            cmp_return_type = self.env.ref('l10n_in_reports.in_cmp08_return_type', raise_if_not_found=False)
            cmp08_returns = self.env['account.return'].search(
                [
                    ('date_from', '>=', options['date']['date_from']),
                    ('date_to', '<=', options['date']['date_to']),
                    ('type_id', '=', cmp_return_type.id),
                ]
            )
            non_filled_cmp08 = cmp08_returns.filtered(lambda cmp08: cmp08.state != 'submitted')
            checks.append({
                'code': 'cmp08_filed',
                'name': _("All CMP-08 Filled"),
                'message': _("All Four CMP-08 statements must be filled before filling GSTR-4"),
                'result': 'anomaly' if non_filled_cmp08 or len(cmp08_returns) != 4 else 'reviewed',
            })

        if 'missing_gst_treatment' not in check_codes_to_ignore:
            partners_without_treatment = self.env['account.move'].search(
                [
                    ('date', '>=', options['date']['date_from']),
                    ('date', '<=', options['date']['date_to']),
                    ('move_type', '!=', 'entry'),
                    ('state', '=', 'posted'),
                    ('l10n_in_gst_treatment', '=', False),
                ]
            ).commercial_partner_id
            checks.append({
                'code': 'missing_gst_treatment',
                'name': _("Missing GST Treatment Type"),
                'message': _("GST Treatment Type set for all contacts"),
                'result': 'anomaly' if partners_without_treatment else 'reviewed',
                'action': partners_without_treatment._get_records_action(
                    name=_("Partners without GST treatment"),
                    views=[(False, 'list'), (False, 'form')],
                    domain=[('id', 'in', partners_without_treatment.ids)]
                ) if partners_without_treatment else None
            })
        return checks

    def _l10n_in_download_gstr1_xlsx(self, attachment_id):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment_id}?download=true',
            'target': 'self',
        }

    def action_generate_gstr1_xlsx(self):
        """
        Generate GSTR-1 XLSX file from the GSTR-1 JSON data.
        This method retrieves the GSTR-1 JSON data, generates an XLSX file,
        and returns the file for download.
        """
        self.ensure_one()
        gstr1_json = self._get_l10n_in_gstr1_json()
        _ = self.env._
        # Generate XLSX
        spreadsheet_generator = GSTR1SpreadsheetGenerator(gstr1_json, self.type_external_id)
        xlsx_data = spreadsheet_generator.generate()
        if self.type_external_id == GSTR_IFF_RETURN_TYPE:
            filename = f'gstr_iff_{self.l10n_in_month_year}_monthly_report.xlsx'
            subject = _("Spreadsheet for GSTR-IFF return")
        else:
            filename = f'gstr1_{self.l10n_in_month_year}_monthly_report.xlsx'
            subject = _("Spreadsheet for GSTR-1 return")

        self.sudo().message_post(
            subject=subject,
            body=_("%s is attached here", subject),
            attachments=[(filename, xlsx_data)],
        )
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'raw': xlsx_data,
            'res_model': 'account.return',
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return self._l10n_in_download_gstr1_xlsx(attachment.id)

    def _prepare_submission(self):
        self.ensure_one()
        if self.type_external_id in (GSTR1_RETURN_TYPE, GSTR_IFF_RETURN_TYPE):
            return self.env['l10n_in.gstr1.submission.wizard']._open_submission_wizard(self)
        else:
            return super()._prepare_submission()

    def action_check_gstr_status(self):
        self.ensure_one()
        if self.type_external_id not in (GSTR1_RETURN_TYPE, GSTR_IFF_RETURN_TYPE):
            return
        if self.l10n_in_gstr1_status != "waiting_for_status":
            raise AccessError(_("To check status please push the GSTN"))
        self._l10n_in_check_config()
        self.check_l10n_in_gstr1_status()

    def action_gstr2b_fetch(self):
        self.ensure_one()
        if self.type_external_id == GSTR2B_RETURN_TYPE:
            self.is_completed = False
            self.action_get_l10n_in_gstr2b_data()

    # ========================================
    # API calls
    # ========================================

    def _l10n_in_reports_request(self, url, company, params=None):
        if not params:
            params = {}
        params.update({
            "username": company.sudo().l10n_in_gstr_gst_username,
            'gstin': company.vat,
        })
        try:
            return self.env['iap.account']._l10n_in_connect_to_server(
                company.sudo().l10n_in_edi_production_env,
                params,
                url,
                "l10n_in_reports.endpoint"
            )
        except RequestException as e:
            _logger.warning("Connection error: %s", e.args[0])
            return {
                "error": [{
                    "code": "404",
                    "message": _("Unable to connect to the GST service."
                        "The web service may be temporary down. Please try again in a moment.")
                }]
            }

    def _l10n_in_gstr_otp_request(self, company):
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/authentication/otprequest", company=company)

    def _l10n_in_gstr_otp_auth_request(self, company, transaction, otp):
        params = {"auth_token": transaction, "otp": otp}
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/authentication/authtoken", params=params, company=company)

    def _l10n_in_refresh_gstr_token_request(self, company):
        params = {"auth_token": company.sudo().l10n_in_gstr_gst_token}
        return self._l10n_in_reports_request(
            url="/iap/l10n_in_reports/1/authentication/refreshtoken", params=params, company=company)

    def _l10n_in_invalidate_gstr_token_request(self, company):
        params = {"auth_token": company.sudo().l10n_in_gstr_gst_token}
        return self._l10n_in_reports_request("/iap/l10n_in_reports/1/authentication/logout", company, params)

    def _l10n_in_send_gstr1_request(self, company, month_year, json_payload):
        params = {
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
            "json_payload": json_payload,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/gstr1/retsave", params=params, company=company)

    def _l10n_in_get_gstr_status_request(self, company, month_year, reference_id):
        params = {
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
            "reference_id": reference_id,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/retstatus", params=params, company=company)

    def _l10n_in_get_gstr2b_data_request(self, company, month_year, file_number=None):
        params = {
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
            "file_number": file_number,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/gstr2b/all", params=params, company=company)

    def _l10n_in_get_einvoice_file_token_request(self, company, month_year, section_code):
        """
        Retrieve the e-invoice file token for the specified return period and section code.

        :param company: The company for which the e-invoice file token is being retrieved.
        :param month_year: The return period in the format 'MM/YYYY'.
        :param section_code: The section code for the e-invoice.

        :returns: The response from the request containing the e-invoice file token.
        """
        params = {
            "ret_period": month_year,
            "suptyp": section_code,
            "gstin": company.vat,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/einvoice/vendor/irnlist", params=params, company=company)

    def _l10n_in_get_einvoice_details_from_file_request(self, company, month_year, token):
        """
        Get details of the e-invoice file using the provided file token.

        :param company: The company requesting the details.
        :param month_year: Return period ('MM/YYYY').
        :param token: E-invoice file token.

        :returns: E-invoice details response.
        """
        params = {
            "ret_period": month_year,
            "gstin": company.vat,
            "file_token": token,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/einvoice/filedtl", params=params, company=company)

    def _l10n_in_gstr_encrypted_large_file_data_request(self, company, month_year, url, encryption_key):
        """
        Retrieve data from an encrypted large file using its URL and encryption key.
        :returns: Decrypted file data response.
        """
        params = {
            "file_url": url,
            "encryption_key": encryption_key,
            "gstin": company.vat,
            "ret_period": month_year,
            "auth_token": company.sudo().l10n_in_gstr_gst_token,
        }
        return self._l10n_in_reports_request(url="/iap/l10n_in_reports/1/all/largefile", params=params, company=company)


class AccountReturnCheck(models.Model):
    _inherit = "account.return.check"

    def action_review(self):
        """
        Create the default document summary only on action click
        for missing_document_summary, (if not already created.)
        """
        if self.code == 'missing_document_summary' and not self.return_id.l10n_in_doc_summary_line_ids:
            self.return_id.action_generate_document_summary()
        return super().action_review()

    def action_get_irn_data_from_check(self):
        self.ensure_one()
        if self.code != 'missing_fetch_einvoice':
            return
        self.return_id.action_l10n_in_get_irn_data()


class AccountReturnCheckTemplate(models.Model):
    _inherit = 'account.return.check.template'

    def _transform_custom_check_template_domain(self, domain):
        check_rules = {
            '_account_return_check_template_in_form_26_cash_accept_us_185': {
                'threshold': 20000,
                'aggregate': 'credit:sum',
                'operator': '>=',
                'group_by_fields': ['partner_id'],
            },
            '_account_return_check_template_in_form_26_cash_repayment_us_188': {
                'threshold': 20000,
                'aggregate': 'debit:sum',
                'operator': '>=',
                'group_by_fields': ['partner_id'],
            },
            '_account_return_check_template_in_form_26_single_cash_receipt_us_186': {
                'threshold': 200000,
                'aggregate': 'debit:sum',
                'operator': '>=',
                'group_by_fields': ['partner_id', 'date:day'],
            },
            '_account_return_check_template_in_form_26_no_single_day_cash_payment_us_36_4': {
                'threshold': 10000,
                'aggregate': 'credit:sum',
                'operator': '>',
                'group_by_fields': ['partner_id', 'date:day'],
            },
        }

        if rule := check_rules.get(self.code):
            cash_aml_ids = []

            for row in self.env['account.move.line'].sudo()._read_group(
                domain=domain,
                groupby=rule['group_by_fields'],
                aggregates=['id:array_agg'],
                having=[(rule['aggregate'], rule['operator'], rule['threshold'])],
            ):
                cash_aml_ids.extend(row[-1])
            return [('id', 'in', cash_aml_ids)]

        return super()._transform_custom_check_template_domain(domain)
