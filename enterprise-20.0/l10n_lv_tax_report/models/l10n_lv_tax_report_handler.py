import json
import re

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import cleanup_xml_node, float_repr, float_round, format_date, SQL
from odoo.tools.business_data import split_vat

_eu_country_vat = {
    'GR': 'EL'
}


class LatvianTaxReportCustomHandler(models.AbstractModel):
    _name = 'l10n_lv.tax.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'Latvian Tax Report Custom Handler'

    @api.model
    def _round_repr_2(self, number):
        if number is None:
            return None
        return float_repr(float_round(number, 2), 2)

    def _get_other_eu_country_codes(self):
        eu_countries = self.env.ref('base.europe').country_ids
        lv = self.env.ref('base.lv')
        return (eu_countries - lv).mapped('code')

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        options.setdefault('buttons', []).append({
            'name': _('XML'),
            'sequence': 30,
            'action': 'open_vat_report_export_wizard',
            'file_export_type': _('XML'),
        })

    def open_vat_report_export_wizard(self, options):
        # Add options to context and return action to open transient model
        new_wizard = self.env['l10n_lv_tax_report.periodic.vat.xml.export'].create({})
        view_id = self.env.ref('l10n_lv_tax_report.view_account_financial_report_export').id
        return {
            'name': _('XML Export Options'),
            'view_mode': 'form',
            'views': [[view_id, 'form']],
            'res_model': 'l10n_lv_tax_report.periodic.vat.xml.export',
            'type': 'ir.actions.act_window',
            'res_id': new_wizard.id,
            'target': 'new',
            'context': dict(self.env.context, l10n_lv_tax_report_generation_options=options),
        }

    def _get_line_value_function(self, options):
        label_to_idx = {col['expression_label']: idx for idx, col in enumerate(options.get('columns', []))}
        return lambda line, label: line.columns[label_to_idx[label]].no_format

    def _get_render_values_for_main_tax_report(self, export_options):
        report = self.env.ref('l10n_lv.l10n_lv_vat_main_tax_report')
        options = report.get_options(export_options)
        lines = report._get_lines(options)

        get_line_value = self._get_line_value_function(options)
        code_map = {
            code: get_line_value(line, 'balance')
            for line in lines
            if (code := get_line_value(line, 'code'))
        }

        # Convert the numbers for the output:
        # - 0 values will be `None` and thus not included in the export
        # - There are 13 digits allowed before the decimal separator and 2 after
        return {
            f"R{code}": self._round_repr_2(balance or None)  # Do not output the tag in case `balance` is 0
            for code, balance in code_map.items()
        }

    def _get_attachment_transactions(self, report, export_options, expression_labels):
        # Return a list of dictionaries with keys `expression_labels`
        # The list contains an item for each line of the `report` (except the first line / the summary line).
        # The values of the keys are extracted directly from the line expressions.
        # :param report: An 'account.report'. One of the lv tax report attachments.
        # :param list: expression_labels: list of expression labels from the `report` lines
        options = report.get_options(export_options)
        options['ignore_totals_below_sections'] = True
        # Remove the first line (header)
        lines = report._get_lines(options)[1:]

        get_line_value = self._get_line_value_function(options)
        return [
            {label: get_line_value(line, label) for label in expression_labels}
            for line in lines
        ]

    @api.model
    def _split_vat_column(self, transaction, vat_label):
        """
        Split the vat number behind label `vat_label` in transaction `transaction`.
        Add keys `f"{vat_label}_country_code"` and `f"{vat_label}_without_country_code" to `transaction`.
        They represent the country code and number without country code of vat number.
        :param transaction: dict: transaction values as a dictionary
        :param vat_label: string: label / key of a vat column / value in `transaction`
        """
        vat = transaction[vat_label]
        if vat:
            vat_country_code, vat_without_country = split_vat(vat)
        else:
            vat_country_code, vat_without_country = False, False
        # The country code should be output according to LVS EN ISO 3166-1:2007
        if vat_country_code:
            vat_country_code = vat_country_code.upper()
        transaction[f'{vat_label}_country_code'] = _eu_country_vat.get(vat_country_code, vat_country_code)
        transaction[f'{vat_label}_without_country_code'] = vat_without_country

    @api.model
    def _convert_float_column_to_string(self, transaction, float_label):
        number = transaction[float_label]
        transaction[float_label] = self._round_repr_2(number or 0)

    def _get_render_values_for_attachment_1i(self, export_options):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_1i')
        expression_labels = [
            'partner_vat',
            'partner_name',
            'transaction_type',
            'base_amount',
            'vat_amount',
            'document_type',
            'document_number',
            'document_date',
        ]
        transactions = self._get_attachment_transactions(report, export_options, expression_labels)
        for transaction in transactions:
            self._split_vat_column(transaction, 'partner_vat')
            self._convert_float_column_to_string(transaction, 'base_amount')
            self._convert_float_column_to_string(transaction, 'vat_amount')
        return transactions

    def _get_render_values_for_attachment_1ii(self, export_options):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_1ii')
        expression_labels = [
            'partner_vat',
            'partner_name',
            'transaction_type',
            'base_amount',
            'vat_amount',
            'base_amount_currency',
            'base_amount_currency_code',
            'document_number',
            'document_date',
        ]
        transactions = self._get_attachment_transactions(report, export_options, expression_labels)
        for transaction in transactions:
            self._split_vat_column(transaction, 'partner_vat')
            self._convert_float_column_to_string(transaction, 'base_amount')
            self._convert_float_column_to_string(transaction, 'vat_amount')
            self._convert_float_column_to_string(transaction, 'base_amount_currency')
        return transactions

    def _get_render_values_for_attachment_1iii(self, export_options):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_1iii')
        expression_labels = [
            'partner_vat',
            'partner_name',
            'vat_declaration_line_number',
            'base_amount',
            'vat_amount',
            'document_type',
            'document_number',
            'document_date',
        ]
        transactions = self._get_attachment_transactions(report, export_options, expression_labels)
        for transaction in transactions:
            self._split_vat_column(transaction, 'partner_vat')
            self._convert_float_column_to_string(transaction, 'base_amount')
            self._convert_float_column_to_string(transaction, 'vat_amount')
        return transactions

    def _get_render_values_for_attachment_2(self, export_options):
        report = self.env.ref('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_attachment_2')
        expression_labels = [
            'partner_vat',
            'base_amount',
            'transaction_type',
            'partner_replacement_vat',
        ]
        transactions = self._get_attachment_transactions(report, export_options, expression_labels)
        for transaction in transactions:
            self._split_vat_column(transaction, 'partner_vat')
            self._split_vat_column(transaction, 'partner_replacement_vat')
            self._convert_float_column_to_string(transaction, 'base_amount')
        return transactions

    def export_tax_report_to_xml(self, options):
        report = self.env['account.report'].browse(options['sections_source_id'])
        options = report.get_options(options)
        period_type = options['date'].get('period_type')

        sender_company = report._get_sender_company_for_export(options)
        report_VAT = report.get_vat_for_export(options)
        report_VAT_country_code, report_VAT_without_country = split_vat(report_VAT)
        default_address = sender_company.partner_id.address_get()
        address = self.env['res.partner'].browse(default_address.get("default")) or sender_company.partner_id

        errors = []
        if not report_VAT:
            errors.append(_('There is no VAT number associated with the report.'))
        elif not self.env['res.partner']._check_vat_number(report_VAT_country_code, report_VAT_without_country):
            errors.append(_('The VAT number associated with the report is invalid: %s', report_VAT))
        if period_type not in {'fiscalyear', 'year', 'month', 'quarter'}:
            errors.append(_("The declaration should be month by month, quarter per quarter or year by year. Please select only a right period."))
        if errors:
            raise UserError('\n'.join(errors))

        date_from = options['date'].get('date_from')
        date_to = options['date'].get('date_to')
        ending_year = format_date(self.env, date_to, date_format='yyyy')
        ending_quarter = format_date(self.env, date_to, date_format='q')
        ending_month = format_date(self.env, date_to, date_format='MM')

        export_options = {
            'no_format': True,
            'date': {'date_from': date_from, 'date_to': date_to},
        }
        options = report.get_options({**options, **export_options})

        render_vals = {
            'year': ending_year,
            'vat_without_country': report_VAT_without_country,
            'phone': re.sub(r"\s+", "", address.phone)[:20],
            'email': address.email[:100],
            'clarification': 'true' if options.get('clarification') else 'false',
            'period_type': period_type,
            'quarter': ending_quarter if period_type == 'quarter' else None,
            'month': ending_month if period_type == 'month' else None,
            'PVN': self._get_render_values_for_main_tax_report(export_options),
            'PVN1I_transactions': self._get_render_values_for_attachment_1i(export_options),
            'PVN1II_transactions': self._get_render_values_for_attachment_1ii(export_options),
            'PVN1III_transactions': self._get_render_values_for_attachment_1iii(export_options),
            'PVN2_transactions': self._get_render_values_for_attachment_2(export_options),
        }

        xml_node = self.env['ir.qweb']._render('l10n_lv_tax_report.l10n_lv_vat_main_tax_report_export', render_vals)
        xml_node = cleanup_xml_node(xml_node, remove_blank_nodes=False, indent_space="    ")
        xml = etree.tostring(xml_node, xml_declaration=True, encoding='UTF-8')

        return {
            'file_name': report.get_default_report_filename(options, 'xml'),
            'file_content': xml,
            'file_type': 'xml',
        }

    def _caret_options_initializer(self):
        return {
            'transaction': [
                # Multiple moves can be grouped together in a single line / transaction (i.e. 'V' and 'T')
                {'name': _("View Journal Items"), 'action': 'caret_option_open_journal_items_from_transaction'},
            ],
        }

    def caret_option_open_journal_items_from_transaction(self, options, params):
        last_id_tuple = self.env['account.report']._parse_line_id(params['line_id'])[-1]
        if last_id_tuple[0] == 'total' or (last_id_tuple[0] or {}).get('groupby') != 'transaction':
            raise UserError(_("'View Journal Items' caret option is only available for report lines targeting transactions."))

        group = json.loads(last_id_tuple[2])
        lines = self.env['account.move.line'].browse(group['line_ids'])
        # We pass `views` and `domain` explicitly to force opening the `lines` in a list view.
        # We should never open account moves lines in a form view.
        return lines._get_records_action(name=_("Journal Items"), views=[(False, "list")], domain=[('id', 'in', lines.ids)])

    def _get_custom_groupby_map(self):
        return {
            'transaction': {
                'model': None,
                'domain_builder': self._groupby_domain_builder,
                'label_builder': self._groupby_label_builder,
                'caret_builder': lambda _grouping_key: 'transaction',
            }
        }

    def _groupby_label_builder(self, grouping_keys):
        # There is no need for a name
        return dict.fromkeys(grouping_keys, "")

    def _groupby_domain_builder(self, grouping_key):
        group = json.loads(grouping_key)
        return [
            ('id', 'in', group['line_ids']),
            ('transaction_type', '=', group['transaction_type']),
        ]

    def _report_engine_l10n_lv_vat_main_tax_report_attachment(
            self, options, date_scope, formulas_dict, current_groupby, warnings=None,
            move_types=None, want_eu_partners=False, transaction_tax_tags=None, aggregate_transaction_type=False, aggregate_document_type=False, transaction_keys=None, main_report_tax_tags=None, document_type_tax_tag_names=None):
        def init_result_dict(res_line=None, transaction_keys=None):
            res_line = res_line or {}
            transaction_keys = transaction_keys or []
            # In case we do not pass `res_line` (e.g. in case of an empty result) we still want the keys in the result dict
            query_keys = [
                'move_id',
                'partner_id',
                'partner_name',
                'partner_vat',
                'transaction_type',
                'base_amount_currency_code',
                'document_number',
                'document_date',
                'document_type',
            ]
            result = {
                **{key: res_line.get(key)for key in query_keys + transaction_keys},
                'base_amount': res_line.get('base_amount') or 0,
                'vat_amount': res_line.get('vat_amount') or 0,
                'base_amount_currency': res_line.get('base_amount_currency'),  # Leave as None for total lines to not render it
                'has_sublines': True,
            }
            return result
        move_types = move_types or []
        transaction_keys = transaction_keys or []
        document_type_tax_tag_names = document_type_tax_tag_names or []  # Only releavant for 1-I and 1-III
        # Supported document types:
        #   (1) Tax Invoice
        #   (2) Cashiers Check or Receipt
        #   (3) Non-Cash Payment Document
        #   (4) Credit Invoice
        #   (5) Other
        #   (6) Customs Declaration  # only for 1-I
        #   (X) Unreportable Transaction  # only for 1-III
        #   (M) Tax Invoice for the Sale of Property at an Auction Organized by a Sworn Bailiff  # only for 1-III
        aggregate_small_transactions = aggregate_transaction_type or aggregate_document_type

        # For representation expenses (and cars) we should only take 40% (or 50% respectively) of the tax and base amount.
        # The tax amount is already split appropriately in the tax definition; but for the base amount that is not really possible.
        # We manually adjust it in the SQL query.
        percentage_tax_tags = self._get_tax_tags([('name', 'in', ('Rep', 'C (car)'))])

        # For the document types 6, X and M we use
        document_type_tax_tags = self._get_tax_tags([('name', 'in', document_type_tax_tag_names)])

        report = self.env['account.report'].browse(options['report_id'])
        if current_groupby:
            report._check_groupby_fields([current_groupby])

        report_query = report._get_report_query(options, 'strict_range')

        select_from_groupby = SQL()
        if current_groupby and current_groupby != 'transaction':
            select_from_groupby = self.env['account.move.line']._field_to_sql('account_move_line', current_groupby, report_query)

        if current_groupby and current_groupby != 'transaction':
            # Raising an error here fails the runbot
            return {next(iter(formulas_dict.values())): init_result_dict(transaction_keys=transaction_keys)}
        transaction_type_expression = SQL("""
                   CASE WHEN transaction.is_small AND partner_info.small_transactions_sum_small
                        THEN 'T'
                        WHEN transaction.is_small
                        THEN 'V'
                        ELSE transaction.transaction_type
                    END
        """) if aggregate_transaction_type else SQL("transaction.transaction_type")
        document_type_expression = SQL(
            """
                   CASE WHEN transaction.document_type_tax_tag_name = 'DokVeids X'
                        THEN 'X'
                        WHEN transaction.is_small AND partner_info.small_transactions_sum_small
                        THEN %(small_transaction_small_partner_document_type)s
                        WHEN transaction.is_small
                        THEN %(small_transaction_not_small_partner_document_type)s
                        WHEN transaction.document_type_tax_tag_name = 'DokVeids 6'
                        THEN '6'
                        WHEN transaction.document_type_tax_tag_name = 'DokVeids M'
                        THEN 'M'
                        WHEN move.move_type IN ('out_invoice', 'in_invoice')
                        THEN '1'
                        WHEN move.move_type IN ('out_receipt', 'in_receipt')
                        THEN '2'
                        WHEN move.move_type = 'entry'
                        THEN '3'
                        WHEN move.move_type IN ('out_refund', 'in_refund')
                        THEN '4'
                        ELSE '5'
                    END
            """,
            small_transaction_small_partner_document_type='T' if aggregate_document_type else None,
            small_transaction_not_small_partner_document_type='V' if aggregate_document_type else None,
        )
        vat_declaration_line_number_expression = SQL("""
                   CASE WHEN (   transaction.main_report_tax_tag_name IS NULL
                              OR transaction.document_type_tax_tag_name = 'DokVeids X'
                              OR transaction.is_small)
                        THEN NULL
                        WHEN transaction.main_report_tax_tag_name = '41'
                        THEN '41'
                        WHEN transaction.main_report_tax_tag_name = '411'
                        THEN '41.1'
                        WHEN transaction.main_report_tax_tag_name = '42'
                        THEN '42'
                        WHEN transaction.main_report_tax_tag_name = '421'
                        THEN '42.1'
                        WHEN transaction.main_report_tax_tag_name IN ('45', '45_G', '45_T', '451', '46', '47', '48', '481')
                        THEN '43'
                        WHEN transaction.main_report_tax_tag_name = '44'
                        THEN '44'
                        WHEN transaction.main_report_tax_tag_name IN ('482', '482_S')
                        THEN '48.2'
                        WHEN transaction.main_report_tax_tag_name = '52'
                        THEN '52'
                        WHEN transaction.main_report_tax_tag_name = '53'
                        THEN '53'
                        WHEN transaction.main_report_tax_tag_name = '531'
                        THEN '53.1'
                        ELSE NULL
                    END
        """)

        query = SQL(
            """
              WITH transaction_line AS (
                  -- This CTE fetches the relevant amls and selects / adds all the necessary information
                  SELECT %(select_from_groupby)s AS grouping_key,
                         account_move_line.id as id,
                         account_move_line.move_id AS move_id,
                         partner.id AS partner_id,
                         SPLIT_PART(transaction_tax_tag.name->>'en_US', ' ', 1) AS transaction_type,
                         repartition_line.id IS NOT NULL AS is_tax,
                         CASE WHEN account_move_line__move_id.move_type = ANY(%(positive_sign_move_types)s)
                              THEN 1
                              ELSE -1
                          END
                             AS sign,
                         CASE WHEN repartition_line.id IS NOT NULL THEN 1  -- only reduce base amount; the tax amount is already split
                              WHEN percentage_tax_tag.name->>'en_US' = 'Rep' THEN 0.4
                              WHEN percentage_tax_tag.name->>'en_US' = 'C (car)' THEN 0.5
                              ELSE 1
                          END
                             AS percentage,
                         account_move_line.amount_currency AS amount_currency,
                         account_move_line.balance AS balance,
                         account_move_line.currency_id AS currency_id,
                         -- Map the tax tags for tax amounts to the corresponding tax tags for base amounts; we remove the sign already
                         CASE WHEN repartition_line.id IS NULL THEN LTRIM(main_report_tax_tag.name->>'en_US', '+-')
                              WHEN LTRIM(main_report_tax_tag.name->>'en_US', '+-') = '52'
                                THEN '41'
                              WHEN LTRIM(main_report_tax_tag.name->>'en_US', '+-') = '53'
                                THEN '42'
                              WHEN LTRIM(main_report_tax_tag.name->>'en_US', '+-') = '53.1'
                                THEN '42.1'
                              ELSE NULL
                          END
                             AS main_report_tax_tag_name,
                         document_type_tax_tag.name->>'en_US' AS document_type_tax_tag_name
                    FROM %(table_references)s
               LEFT JOIN res_partner partner
                      ON COALESCE(account_move_line__move_id.partner_shipping_id, account_move_line.partner_id) = partner.id
               LEFT JOIN res_country partner_country
                      ON partner.country_id = partner_country.id
               LEFT JOIN account_tax_repartition_line repartition_line
                      ON account_move_line.tax_repartition_line_id = repartition_line.id
               LEFT JOIN account_account_tag_account_move_line_rel transaction_tax_tag_rel
                      ON transaction_tax_tag_rel.account_move_line_id = account_move_line.id
                         %(and_transaction_tax_tags_condition)s
               LEFT JOIN account_account_tag transaction_tax_tag
                      ON transaction_tax_tag.id = transaction_tax_tag_rel.account_account_tag_id
               LEFT JOIN account_account_tag_account_move_line_rel main_report_tax_tag_rel
                      ON main_report_tax_tag_rel.account_move_line_id = account_move_line.id
                         %(and_main_report_tax_tags_condition)s
               LEFT JOIN account_account_tag main_report_tax_tag
                      ON main_report_tax_tag.id = main_report_tax_tag_rel.account_account_tag_id
               LEFT JOIN account_account_tag_account_move_line_rel percentage_tax_tag_rel
                      ON percentage_tax_tag_rel.account_move_line_id = account_move_line.id
                         %(and_percentage_tax_tags_condition)s
               LEFT JOIN account_account_tag percentage_tax_tag
                      ON percentage_tax_tag.id = percentage_tax_tag_rel.account_account_tag_id
               LEFT JOIN account_account_tag_account_move_line_rel document_type_tax_tag_rel
                      ON document_type_tax_tag_rel.account_move_line_id = account_move_line.id
                         %(and_document_type_tax_tags_condition)s
               LEFT JOIN account_account_tag document_type_tax_tag
                      ON document_type_tax_tag.id = document_type_tax_tag_rel.account_account_tag_id
                   WHERE %(search_condition)s
                     AND (transaction_tax_tag.id IS NOT NULL OR main_report_tax_tag.id IS NOT NULL)
                     AND account_move_line__move_id.move_type = ANY(%(move_types)s)
                     AND (partner_country.code = ANY(%(eu_country_codes)s)) = %(want_eu_partners)s
            ),
                   transaction AS (
                  -- This CTE groups the amls from transaction_line into individual transactions
                  -- (but we do not aggregate small transactions yet)
                  SELECT transaction_line.grouping_key AS grouping_key,
                         -- We use a string because there is no function to aggregate arrays in a GROUP BY
                         STRING_AGG(transaction_line.id::text, ',') AS account_move_line_ids_string,
                         transaction_line.move_id AS move_id,
                         transaction_line.partner_id AS partner_id,
                         transaction_line.transaction_type AS transaction_type,
                         transaction_line.currency_id,
                         transaction_line.main_report_tax_tag_name,
                         -- We only support a single "special" document type tag per move
                         MIN(transaction_line.document_type_tax_tag_name) AS document_type_tax_tag_name,
                         ABS(SUM(CASE WHEN transaction_line.is_tax
                                      THEN 0
                                      ELSE transaction_line.amount_currency * transaction_line.sign * transaction_line.percentage
                                  END))
                             AS base_amount_currency,
                         ABS(SUM(CASE WHEN transaction_line.is_tax
                                      THEN 0
                                      ELSE transaction_line.balance * transaction_line.sign * transaction_line.percentage
                                  END))
                             AS base_amount,
                         ROUND(ABS(SUM(CASE WHEN transaction_line.is_tax
                                      THEN 0
                                      ELSE transaction_line.balance * transaction_line.sign * transaction_line.percentage
                                  END)),
                               %(report_currency_decimal_places)s) < 150
                             AS is_small,
                         ABS(SUM(CASE WHEN transaction_line.is_tax
                                      THEN transaction_line.balance * transaction_line.sign * transaction_line.percentage
                                      ELSE 0
                                  END))
                             AS vat_amount
                    FROM transaction_line
                GROUP BY transaction_line.grouping_key,
                         transaction_line.move_id,
                         transaction_line.partner_id,
                         transaction_line.transaction_type,
                         transaction_line.currency_id,
                         transaction_line.main_report_tax_tag_name
            ),
                   partner_info AS (
                  -- This CTE gives info about the total of the transaction partners
                  SELECT transaction.partner_id AS partner_id,
                         ROUND(SUM(ABS(CASE WHEN base_amount < 150 THEN base_amount ELSE 0 END)),
                               %(report_currency_decimal_places)s) < 150
                             AS small_transactions_sum_small
                    FROM transaction
                GROUP BY transaction.partner_id
            )
            SELECT transaction.grouping_key AS grouping_key,
                   STRING_TO_ARRAY(STRING_AGG(transaction.account_move_line_ids_string, ','), ',') AS line_ids,
                   move.id AS move_id,
                   partner.id AS partner_id,
                   partner.name AS partner_name,
                   partner.vat AS partner_vat,
                   %(transaction_type_expression)s AS transaction_type,
                   res_currency.name AS base_amount_currency_code,
                   SUM(ABS(transaction.base_amount_currency)) AS base_amount_currency,
                   SUM(ABS(transaction.base_amount)) AS base_amount,
                   SUM(ABS(transaction.vat_amount)) AS vat_amount,
                   move.name AS document_number,
                   move.date AS document_date,
                   %(document_type_expression)s AS document_type,
                   transaction.main_report_tax_tag_name AS main_report_tax_tag_name,
                   %(vat_declaration_line_number_expression)s AS vat_declaration_line_number
              FROM transaction
         LEFT JOIN partner_info
                ON transaction.partner_id = partner_info.partner_id
         LEFT JOIN res_currency
                ON res_currency.id = transaction.currency_id
         LEFT JOIN account_move move
                ON move.id = transaction.move_id
               AND (transaction.document_type_tax_tag_name IS NULL OR transaction.document_type_tax_tag_name != 'DokVeids X')
               AND (%(join_move_condition)s)
         LEFT JOIN res_partner partner
                ON transaction.partner_id = partner.id
               AND (%(join_partner_condition)s)
          GROUP BY transaction.grouping_key,
                   move.id,
                   partner.id,
                   partner_name,
                   partner_vat,
                   %(transaction_type_expression)s,
                   base_amount_currency_code,
                   document_number,
                   document_date,
                   %(document_type_expression)s,
                   transaction.main_report_tax_tag_name,
                   %(vat_declaration_line_number_expression)s
          ORDER BY transaction.grouping_key,
                   move.id,
                   partner.id,
                   %(transaction_type_expression)s,
                   %(document_type_expression)s,
                   %(vat_declaration_line_number_expression)s
            """,
            select_from_groupby=select_from_groupby or '',
            table_references=report_query.from_clause,
            search_condition=report_query.where_clause,
            positive_sign_move_types=(['entry'] + self.env['account.move'].get_outbound_types(include_receipts=True)),
            report_currency_decimal_places=2,  # We only have 2 decimal places in the report
            move_types=move_types,
            eu_country_codes=self._get_other_eu_country_codes(),
            want_eu_partners=want_eu_partners,
            and_transaction_tax_tags_condition=SQL("AND transaction_tax_tag_rel.account_account_tag_id = ANY(%s)", transaction_tax_tags.ids) if transaction_tax_tags else SQL("AND FALSE"),
            and_main_report_tax_tags_condition=SQL("AND main_report_tax_tag_rel.account_account_tag_id = ANY(%s)", main_report_tax_tags.ids) if main_report_tax_tags else SQL("AND FALSE"),
            and_percentage_tax_tags_condition=SQL("AND percentage_tax_tag_rel.account_account_tag_id = ANY(%s)", percentage_tax_tags.ids) if percentage_tax_tags else SQL("AND FALSE"),
            and_document_type_tax_tags_condition=SQL("AND document_type_tax_tag_rel.account_account_tag_id = ANY(%s)", document_type_tax_tags.ids) if document_type_tax_tags else SQL("AND FALSE"),
            join_move_condition=SQL("NOT transaction.is_small") if aggregate_small_transactions else SQL("TRUE"),
            join_partner_condition=SQL("NOT transaction.is_small OR NOT partner_info.small_transactions_sum_small") if aggregate_small_transactions else SQL("TRUE"),
            transaction_type_expression=transaction_type_expression,
            document_type_expression=document_type_expression,
            vat_declaration_line_number_expression=vat_declaration_line_number_expression,
        )

        self.env.cr.execute(query)
        query_results = self.env.cr.dictfetchall()

        if current_groupby:
            # Extract the group; add the `line_ids` to the group and JSON-ify the group.
            rslt = [
                (json.dumps({
                     **{key: res_line.get(key)for key in transaction_keys},
                     'line_ids': res_line['line_ids'],
                 }),
                 init_result_dict(res_line, transaction_keys=transaction_keys))
                for res_line in query_results
            ]
            return {next(iter(formulas_dict.values())): rslt}

        rslt_dict = init_result_dict(transaction_keys=transaction_keys)
        for res_line in query_results:
            rslt_dict['base_amount'] += res_line['base_amount'] or 0
            rslt_dict['vat_amount'] += res_line['vat_amount'] or 0
            # The base_amount_currency could be from mixed currencies so we do not make a sum
        return {next(iter(formulas_dict.values())): rslt_dict}

    @api.model
    def _get_tax_tags(self, name_domain):
        # Adapted from `_get_tax_tags` from model 'account.account.tag'
        original_lang = self.env.context.get('lang', 'en_US')
        base_domain = [
            ('country_id', '=', 'LV'),
            ('applicability', '=', 'taxes'),
        ]
        rslt_tags = self.env['account.account.tag'].with_context(active_test=False, lang='en_US').search(
            Domain.AND([name_domain, base_domain]),
        )
        return rslt_tags.with_context(lang=original_lang)  # Restore original language, in case the name of the tags needs to be shown/modified

    def _report_engine_l10n_lv_vat_main_tax_report_attachment_1i(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        # Transactions are identified by `move_id` and `transaction_type`.
        # But we aggregate small transactions per partner / globally; they have special `transaction_type` values:
        # - 'V': Transactions with a single partner with base amount < 150€ that total at least 150€
        #        (there is max one line per partner in the report)
        # - 'T': Transactions with base amount < 150€ (that are not 'V')
        #        (there is max one line in the report)

        transaction_tag_names = ['I', 'A', 'C (car)', 'N (no VAT)', 'K', 'Z', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'M']
        l10n_lv_options = {
            'move_types': self.env['account.move'].get_purchase_types(include_receipts=True),
            'want_eu_partners': False,
            'transaction_tax_tags': self._get_tax_tags([('name', 'in', transaction_tag_names)]),
            'aggregate_transaction_type': True,
            'transaction_keys': ['move_id', 'partner_id', 'transaction_type'],
            'document_type_tax_tag_names': ['DokVeids 6'],
        }
        return self._report_engine_l10n_lv_vat_main_tax_report_attachment(
            options, date_scope, formulas_dict, current_groupby, warnings=None, **l10n_lv_options,
        )

    def _report_engine_l10n_lv_vat_main_tax_report_attachment_1ii(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        # Transactions are identified by `move_id` and `transaction_type`.
        # But we aggregate small transactions per partner / globally; they have special `transaction_type` values:
        # - 'V': Transactions with a single partner with base amount < 150€ that total at least 150€
        #        (there is max one line per partner in the report)
        # - 'T': Transactions with base amount < 150€ (that are not 'V')
        #        (there is max one line in the report)
        transaction_tag_names = ['P', 'G', 'C (art. 9)']
        l10n_lv_options = {
            'transaction_tax_tags': self._get_tax_tags([('name', 'in', transaction_tag_names)]),
            'want_eu_partners': True,
            'aggregate_transaction_type': True,
            'transaction_keys': ['move_id', 'partner_id', 'transaction_type'],
            'move_types': self.env['account.move'].get_purchase_types(include_receipts=True),
        }
        return self._report_engine_l10n_lv_vat_main_tax_report_attachment(
            options, date_scope, formulas_dict, current_groupby, warnings=None, **l10n_lv_options,
        )

    def _report_engine_l10n_lv_vat_main_tax_report_attachment_1iii(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        # Transactions are identified by `move_id` and `document_type` and `vat_declaration_line_number`.
        # But we aggregate some transactions; they have special `document_type` values:
        # - 'V': Transactions with a single partner with base amount < 150€ that total at least 150€
        #        (there is max one line per partner in the report)
        # - 'T': Transactions with base amount < 150€ (that are not 'V')
        #        (there is max one line in the report)
        # - 'X': Transactions with `document_type` 'X'
        #        (there is max one line in the report)
        # (And we ignore the `vat_declaration_line_number` for such aggregations.)
        main_report_tax_tag_names = [
            '41', '411', '42', '421', '45', '45_G', '45_T', '451', '46', '47', '48', '481', '44', '482', '482_S', '52', '53', '531',
        ]
        l10n_lv_options = {
            'transaction_tax_tags': self.env['account.account.tag'],
            'main_report_tax_tags': self._get_tax_tags([('name', 'in', main_report_tax_tag_names)]),
            'want_eu_partners': False,
            'aggregate_document_type': True,
            'transaction_keys': ['move_id', 'partner_id', 'document_type', 'vat_declaration_line_number'],
            'move_types': self.env['account.move'].get_sale_types(include_receipts=True),
            'document_type_tax_tag_names': ['DokVeids X', 'DokVeids M'],
        }
        return self._report_engine_l10n_lv_vat_main_tax_report_attachment(
            options, date_scope, formulas_dict, current_groupby, warnings=None, **l10n_lv_options,
        )

    def _report_engine_l10n_lv_vat_main_tax_report_attachment_2(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        # Transactions are identified by `move_id` and `transaction_type` and the partner info.
        # NOTE: the `partner_replacement_vat` is not implemented / used currently.
        # (We do not aggregate transactions in any way here.)

        transaction_tag_names = ['S', 'P', 'G', 'C (art. 45)', 'N (art 31.1)', 'E1', 'E2', 'E3', 'E4']
        l10n_lv_options = {
            'transaction_tax_tags': self._get_tax_tags([('name', 'in', transaction_tag_names)]),
            'want_eu_partners': True,
            'transaction_keys': ['move_id', 'partner_id', 'transaction_type', 'partner_replacement_vat'],
            'move_types': self.env['account.move'].get_sale_types(include_receipts=True),
        }
        vals = self._report_engine_l10n_lv_vat_main_tax_report_attachment(
            options, date_scope, formulas_dict, current_groupby, warnings=None, **l10n_lv_options,
        )
        return vals
