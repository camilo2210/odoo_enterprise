import csv
import datetime
import io
from itertools import chain
from typing import Literal

import odoo.release
from odoo import api, models
from odoo.tools import SQL, float_repr, format_list

FAF_VERSION = "FAFv1.0.0"


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        if self.env.company.account_fiscal_country_id.code == 'AE':
            options.setdefault('buttons', []).append({
                'name': self.env._('FAF'),
                'sequence': 50,
                'action': 'export_file',
                'action_param': 'l10n_ae_export_faf_csv',
                'file_export_type': self.env._('CSV'),
            })

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        super()._customize_warnings(report, options, all_column_groups_expression_totals, warnings)
        company = self.env.company
        args = []
        if company.account_fiscal_country_id.code != 'AE':
            return

        if not company.l10n_ae_name_ar:
            args.append(self.env._("Arabic Name"))

        if not company.vat:
            args.append(self.env._("TRN"))

        if args:
            warnings['l10n_ae_faf.company_data_warning'] = {
                'alert_type': 'warning',
                'args': format_list(self.env, args),
            }

    def action_fill_company_details(self, options, params):
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Missing company details.'),
            'res_model': 'res.company',
            'views': [(False, 'form')],
            'res_id': self.env.company.id,
        }

    @api.model
    def _l10n_ae_faf_sanitize_str(self, val):
        return (val and val.replace(',', ';')) or ''

    @api.model
    def _l10n_ae_faf_sanitize_date(self, val):
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val.strftime('%d-%m-%Y')
        if isinstance(val, str):
            return datetime.datetime.strptime(val, '%Y-%m-%d').strftime('%d-%m-%Y')

        return '31-12-9999'  # Default Date

    @api.model
    def _l10n_ae_faf_sanitize_float(self, val):
        return float_repr(float(val), precision_digits=2)

    @api.model
    def _l10n_ae_faf_sanitize_int(self, val):
        return val or '0'

    @api.model
    def l10n_ae_export_faf_csv(self, options):
        report = self.env['account.report'].browse(options['report_id'])
        vals = self._l10n_ae_prepare_faf_report_vals(report, options)
        return report._generate_file_data_with_error_check(
            options,
            self._l10n_ae_csv_generator,
            {'lines': vals.get('lines'), 'file_type': 'csv'},
            vals.get('errors', []),
        )

    @api.model
    def _l10n_ae_csv_generator(self, lines, **kwargs):
        with io.StringIO() as buf:
            writer = csv.writer(buf, delimiter=',')
            writer.writerows(lines)
            return buf.getvalue()

    @api.model
    def _l10n_ae_prepare_faf_report_vals(self, report, options):
        vals = self._l10n_ae_faf_fetch_data(report, options)
        errors = self._l10n_ae_faf_get_errors(vals)
        lines = self._l10n_ae_faf_get_lines(vals)
        return {
            'errors': errors,
            'lines': lines,
        }

    @api.model
    def _l10n_ae_faf_fetch_data(self, report, options):
        res = {
            'moves': {},
            'partners': {},
            'taxes': {},
            'date_from': options['date']['date_from'],
            'date_to': options['date']['date_to'],
            'company': self.env.company,
        }

        query = self._l10n_ae_faf_get_data_query(report, options)
        move_lines = self.env.execute_query_dict(query)
        inbound_types = self.env['account.move'].get_inbound_types()

        for line in move_lines:
            if (partner := line['partner_id']) and not res['partners'].get(partner):
                res['partners'][partner] = {
                    'id': partner,
                    'name': line['partner_name'],
                    'vat': line['partner_vat'],
                    'country_id': line['partner_country_id'],
                    'country_name': line['partner_country_name'],
                    'country_code': line['partner_country_code'],
                    'state_id': line['partner_state_id'],
                    'state_name': line['partner_state_name'],
                }
            if (partner := line['delivery_partner_id']) and not res['partners'].get(partner):
                res['partners'][partner] = {
                    'id': partner,
                    'name': line['delivery_partner_name'],
                    'vat': line['delivery_partner_vat'],
                    'country_id': line['delivery_partner_country_id'],
                    'country_name': line['delivery_partner_country_name'],
                    'country_code': line['delivery_partner_country_code'],
                    'state_id': line['delivery_partner_state_id'],
                    'state_name': line['delivery_partner_state_name'],
                }
            if not res['moves'].get(line['move_id']):
                res['moves'][line['move_id']] = {
                    'id': line['move_id'],
                    'name': line['move_name'],
                    'type': line['move_type'],
                    'l10n_ae_import_permit_number': line['l10n_ae_import_permit_number'],
                    'partner_id': line['partner_id'],
                    'partner_country_code': line['partner_country_code'],
                    'delivery_partner_id': line['delivery_partner_id'],
                    'lines': {},
                    'sign': -1 if line['move_type'] in inbound_types else 1,
                }
            for tax in line['taxes'] or []:
                if not res['taxes'].get(tax['id']):
                    res['taxes'][tax['id']] = {
                        'id': tax['id'],
                        'name': tax['name'],
                        'amount': tax['amount'],
                        'amount_type': tax['amount_type'],
                        'l10n_ae_tax_code': tax['l10n_ae_tax_code'],
                    }
            res['moves'][line['move_id']]['lines'][line['id']] = {
                **line,
                'tax_details': [],
            }

        rows = self.env.execute_query_dict(self._get_tax_details_query(report, options))
        for tax_vals in rows:
            res['moves'][tax_vals['move_id']]['lines'][tax_vals['base_line_id']]['tax_details'].append(tax_vals)
        return res

    @api.model
    def _l10n_ae_faf_get_data_query(self, report, options):
        query = report._get_report_query(options, 'strict_range')
        tax_name = self.env['account.tax']._field_to_sql('tax', 'name')
        account_code = self.env['account.account']._field_to_sql('account', 'code')
        account_name = self.env['account.account']._field_to_sql('account', 'name')
        partner_country_name = self.env['res.country']._field_to_sql('partner_country', 'name')
        partner_state_name = self.env['res.country.state']._field_to_sql('partner_state', 'name')
        delivery_partner_country_name = self.env['res.country']._field_to_sql('delivery_partner_country', 'name')
        delivery_partner_state_name = self.env['res.country.state']._field_to_sql('delivery_partner_state', 'name')
        product_name = self.env['product.template']._field_to_sql('product_template', 'name')

        return SQL(
            """
            SELECT
                account_move_line.id,
                account_move_line.display_type,
                account_move_line.date,
                CONCAT_WS('\n', %(product_name)s, account_move_line.name) AS name,
                account_move_line.account_id,
                account_move_line.currency_id,
                account_move_line.amount_currency,
                account_move_line.debit,
                account_move_line.credit,
                account_move_line.balance,
                account_move_line.tax_line_id,
                account_move_line.partner_id,
                account_move_line.price_subtotal,
                account_move_line.ref,
                partner.name                                AS partner_name,
                partner.vat                                 AS partner_vat,
                partner.state_id                            AS partner_state_id,
                %(partner_state_name)s                      AS partner_state_name,
                partner.country_id                          AS partner_country_id,
                %(partner_country_name)s                    AS partner_country_name,
                partner_country.code                        AS partner_country_code,
                delivery_partner.state_id                   AS delivery_partner_state_id,
                %(delivery_partner_state_name)s             AS delivery_partner_state_name,
                delivery_partner.country_id                 AS delivery_partner_country_id,
                %(delivery_partner_country_name)s           AS delivery_partner_country_name,
                delivery_partner_country.code               AS delivery_partner_country_code,
                account_move.id                             AS move_id,
                account_move.name                           AS move_name,
                account_move.move_type                      AS move_type,
                account_move.l10n_ae_import_permit_number   AS l10n_ae_import_permit_number,
                account_move.partner_shipping_id            AS delivery_partner_id,
                (
                    SELECT json_agg(
                            json_build_object(
                                'id', tax.id,
                                'name', %(tax_name)s,
                                'amount', tax.amount,
                                'amount_type', tax.amount_type,
                                'l10n_ae_tax_code', tax.l10n_ae_tax_code
                            )
                        )
                    FROM account_move_line_account_tax_rel aml_tax
                    JOIN account_tax tax ON tax.id = aml_tax.account_tax_id
                    WHERE aml_tax.account_move_line_id = account_move_line.id
                ) AS taxes,
                account.account_type                        AS account_type,
                %(account_name)s                            AS account_name,
                %(account_code)s                            AS account_code,
                currency.name                               AS currency_code
            FROM %(table_references)s
            JOIN account_move ON account_move.id = account_move_line.move_id
            JOIN account_account account ON account.id = account_move_line.account_id
            JOIN res_currency currency ON currency.id = account_move_line.currency_id
            LEFT JOIN res_partner partner ON partner.id = account_move.partner_id
            LEFT JOIN res_country partner_country ON partner_country.id = partner.country_id
            LEFT JOIN res_country_state partner_state ON partner_state.id = partner.state_id
            LEFT JOIN res_partner delivery_partner ON delivery_partner.id = account_move.partner_shipping_id
            LEFT JOIN res_country delivery_partner_country ON delivery_partner_country.id = delivery_partner.country_id
            LEFT JOIN res_country_state delivery_partner_state ON delivery_partner_state.id = delivery_partner.state_id
            LEFT JOIN product_product product ON product.id = account_move_line.product_id
            LEFT JOIN product_template product_template ON product_template.id = product.product_tmpl_id
            WHERE %(search_condition)s
            ORDER BY account_move_line.date, account_move_line.id
            """,
            tax_name=tax_name,
            account_code=account_code,
            account_name=account_name,
            partner_country_name=partner_country_name,
            partner_state_name=partner_state_name,
            delivery_partner_country_name=delivery_partner_country_name,
            delivery_partner_state_name=delivery_partner_state_name,
            table_references=query.from_clause,
            search_condition=query.where_clause,
            product_name=product_name,
        )

    @api.model
    def _get_tax_details_query(self, report, options):
        query = report._get_report_query(options, 'strict_range')
        tax_details_query = self.env['account.move.line']._get_query_tax_details(query)
        tax_name = self.env['account.tax']._field_to_sql('tax', 'name')

        return SQL("""
            SELECT
                tax_detail.base_line_id,
                tax_line.move_id,
                tax_line.currency_id,
                tax.id AS tax_id,
                tax.type_tax_use AS tax_type,
                tax.amount_type AS tax_amount_type,
                %(tax_name)s AS tax_name,
                tax.amount AS tax_amount,
                tax.tax_group_id AS tax_group,
                tax.create_date AS tax_create_date,
                SUM(tax_detail.tax_amount) AS amount,
                SUM(tax_detail.tax_amount) AS amount_currency
            FROM (%(tax_details_query)s) AS tax_detail
            JOIN account_move_line tax_line ON tax_line.id = tax_detail.tax_line_id
            JOIN account_tax tax ON tax.id = tax_detail.tax_id
            WHERE SIGN(tax_detail.tax_amount) = SIGN(tax_detail.base_amount)
            GROUP BY tax_line.move_id, tax_detail.base_line_id, tax_line.currency_id, tax.id
        """, tax_name=tax_name, tax_details_query=tax_details_query)

    @api.model
    def _l10n_ae_faf_get_errors(self, vals):
        company = vals['company']
        errors = {}

        if missing_code_taxes := [tax_id for tax_id, tax in vals['taxes'].items() if not tax['l10n_ae_tax_code']]:
            errors['l10n_ae_tax_missing_categ_code'] = {
                'message': self.env._("Please define the Tax Codes on the Taxes"),
                'action_text': self.env._("View Taxes"),
                'action': self.env['account.tax'].browse(missing_code_taxes)._get_records_action(),
                'level': 'warning',
            }

        if missing_permit_moves := [move_id for move_id, move in vals['moves'].items()
                                    if move['type'] in self.env['account.move'].get_purchase_types()
                                    and move['partner_country_code'] != 'AE'
                                    and not move['l10n_ae_import_permit_number']]:
            errors['l10n_ae_move_missing_permit'] = {
                'message': self.env._("Please define the Import Permit Number on the vendor bills if needed"),
                'action_text': self.env._("View Vendor Bills"),
                'action': self.env['account.move'].browse(missing_permit_moves)._get_records_action(),
                'level': 'warning',
            }

        if missing_state_partners := [partner_id for partner_id, partner in vals['partners'].items()
                                      if partner['country_code'] == 'AE'
                                      and not partner['state_id']]:
            errors['l10n_ae_partner_missing_state'] = {
                'message': self.env._("Please input the 'State' for the following partners"),
                'action_text': self.env._("View Contacts"),
                'action': self.env['res.partner'].browse(missing_state_partners)._get_records_action(),
                'level': 'warning',
            }

        if company.l10n_ae_tax_agent and not company.l10n_ae_tax_agent.ref:
            errors['l10n_ae_tax_agent_missing_ref'] = {
                'message': self.env._("Please define the Tax Agent Approval Number on the \"Reference\" for the Tax Agent"),
                'action_text': self.env._("View Tax Agent"),
                'action': company.l10n_ae_tax_agent._get_records_action(),
                'level': 'warning',
            }

        if company.l10n_ae_tax_agency and not company.l10n_ae_tax_agency.l10n_ae_tax_agency_number:
            errors['l10n_ae_tax_agency_missing_company_registry'] = {
                'message': self.env._("Please define the Tax Agency Number on the \"Company ID\" for the Tax Agency"),
                'action_text': self.env._("View Tax Agency"),
                'action': company.l10n_ae_tax_agency._get_records_action(),
                'level': 'warning',
            }

        return errors

    @api.model
    def _l10n_ae_faf_get_company_info_lines(self, vals, lines):
        company = vals['company']

        lines.extend([
            # Start
            ('Company Information Table', ),
            # Table Headers
            ('TaxablePersonNameEn',
             'TaxablePersonNameAr',
             'TRN',
             'TaxAgencyName',
             'TAN',
             'TaxAgentName',
             'TAAN',
             'PeriodStart',
             'PeriodEnd',
             'FAFCreationDate',
             'ProductVersion',
             'FAFVersion',
            ),
            # Table Rows
            (company.name,
             self._l10n_ae_faf_sanitize_str(company.l10n_ae_name_ar),
             self._l10n_ae_faf_sanitize_str(company.vat),
             self._l10n_ae_faf_sanitize_str(company.l10n_ae_tax_agency.name),
             self._l10n_ae_faf_sanitize_str(company.l10n_ae_tax_agency.l10n_ae_tax_agency_number),
             self._l10n_ae_faf_sanitize_str(company.l10n_ae_tax_agent.name),
             self._l10n_ae_faf_sanitize_str(company.l10n_ae_tax_agent.ref),
             self._l10n_ae_faf_sanitize_date(vals['date_from']),
             self._l10n_ae_faf_sanitize_date(vals['date_to']),
             self._l10n_ae_faf_sanitize_date(datetime.datetime.today()),
             odoo.release.product_name + ' ' + odoo.release.version,
             FAF_VERSION,
            ),
            # Empty Line
            (None, ),
        ])

    @api.model
    def _l10n_ae_faf_get_lines(self, vals):
        lines = {
            'company_info': [],
            'customer_supply': [],
            'supplier_purchase': [],
            'general_ledger': [],
        }

        running_totals = {
            'supplier_purchase_total': 0,
            'supplier_purchase_vat': 0,
            'supplier_purchase_count': 0,
            'customer_supply_total': 0,
            'customer_supply_vat': 0,
            'customer_supply_count': 0,
            'general_ledger_debit': 0,
            'general_ledger_credit': 0,
            'general_ledger_count': 0,
            'general_ledger_currency': vals['company'].currency_id.name,
        }

        self._l10n_ae_faf_get_company_info_lines(vals, lines['company_info'])
        self._l10n_ae_faf_prepare_table_headers(lines)

        # Table Rows
        for move in vals['moves'].values():
            if move['type'] in self.env['account.move'].get_purchase_types():
                self._l10n_ae_faf_prepare_supply_lines('purchase', move, lines['supplier_purchase'], running_totals)

            elif move['type'] in self.env['account.move'].get_sale_types():
                self._l10n_ae_faf_prepare_supply_lines('sale', move, lines['customer_supply'], running_totals)

            self._l10n_ae_faf_prepare_general_ledger_lines(move, lines['general_ledger'], running_totals)

        # Prepare table totals
        self._l10n_ae_faf_prepare_purchase_totals(lines, running_totals)
        self._l10n_ae_faf_prepare_sale_totals(lines, running_totals)
        self._l10n_ae_faf_prepare_general_ledger_totals(lines, running_totals)

        return list(chain.from_iterable(lines.values()))

    @api.model
    def _l10n_ae_faf_prepare_table_headers(self, lines):
        # Start
        lines['supplier_purchase'].extend([
            ('Supplier Purchase Listing Table', ),
            # Table Headers
            ('SupplierName',
             'SupplierCountry',
             'SupplierTIN/TRN',
             'InvoiceDate',
             'Invoice No',
             'PermitNo',
             'TransactionID',
             'Line No.',
             'ProductDescription',
             'PurchaseValueAED',
             'VATValueAED',
             'TaxCode',
             'FCYCode',
             'PurchaseFCY',
             'VATFCY',
        ),
        ])
        lines['customer_supply'].extend([
            ('Customer Supply Listing Table', ),
            # Table Headers
            ('Customer Name',
             'CustomerCountry',
             'CustomerTIN/TRN',
             'InvoiceDate',
             'Invoice No',
             'TransactionID',
             'Line No.',
             'ProductDescription',
             'SupplyValueAED',
             'VATValueAED',
             'TaxCode',
             'Country',
             'FCYCode',
             'SupplyFCY',
             'VATFCY',
        ),
        ])
        lines['general_ledger'].extend([
            ('General Ledger Table', ),
            # Table Headers
            ('TransactionDate',
             'AccountID',
             'AccountName',
             'TransactionDescription',
             'Name',
             'TransactionID',
             'SourceDocumentID',
             'SourceType',
             'Debit',
             'Credit',
             'Balance',
        ),
        ])

    @api.model
    def _l10n_ae_faf_prepare_purchase_totals(self, lines, running_totals):
        lines['supplier_purchase'].extend([
            (None, ),
            ('Supplier Purchase Listing Total', ),
            ('TransactionCountTotal',
             'PurchaseTotalAED',
             'VATTotalAED',
            ),
            (self._l10n_ae_faf_sanitize_int(running_totals['supplier_purchase_count']),
             self._l10n_ae_faf_sanitize_float(running_totals['supplier_purchase_total']),
             self._l10n_ae_faf_sanitize_float(running_totals['supplier_purchase_vat']),
            ),
            (None, ),
        ])

    @api.model
    def _l10n_ae_faf_prepare_sale_totals(self, lines, running_totals):
        lines['customer_supply'].extend([
            (None, ),
            ('Customer Supply Listing Total', ),
            ('TransactionCountTotal',
             'SupplyTotalAED',
             'VATTotalAED',
            ),
            (self._l10n_ae_faf_sanitize_int(running_totals['customer_supply_count']),
             self._l10n_ae_faf_sanitize_float(running_totals['customer_supply_total']),
             self._l10n_ae_faf_sanitize_float(running_totals['customer_supply_vat']),
            ),
            (None, ),
        ])

    @api.model
    def _l10n_ae_faf_prepare_general_ledger_totals(self, lines, running_totals):
        lines['general_ledger'].extend([
            (None, ),
            ('General Ledger Table Total', ),
            ('TotalDebit',
             'TotalCredit',
             'TransactionCountTotal',
             'GLTCurrency',
            ),
            (self._l10n_ae_faf_sanitize_float(running_totals['general_ledger_debit']),
             self._l10n_ae_faf_sanitize_float(running_totals['general_ledger_credit']),
             self._l10n_ae_faf_sanitize_int(running_totals['general_ledger_count']),
             self._l10n_ae_faf_sanitize_str(running_totals['general_ledger_currency']),
            ),
            (None, ),
        ])

    @api.model
    def _l10n_ae_faf_prepare_supply_lines(self, line_type: Literal['sale', 'purchase'], move_vals, lines, running_totals):
        lines_to_add = []
        for line_no, line_vals in enumerate(
            filter(lambda line: line['display_type'] == 'product', move_vals['lines'].values()), start=1,
        ):
            tax_details = line_vals['tax_details']
            tax_amount = abs(sum(tax['amount'] for tax in tax_details))
            tax_amount_currency = abs(sum(tax['amount_currency'] for tax in tax_details))
            l10n_ae_tax_code = ' '.join(tax['l10n_ae_tax_code'] for tax in line_vals['taxes'] or [] if tax['l10n_ae_tax_code'])
            partner_country = line_vals['partner_state_name'] if line_vals['partner_country_code'] == 'AE' else line_vals['partner_country_name']
            line = (
                self._l10n_ae_faf_sanitize_str(line_vals['partner_name']),
                self._l10n_ae_faf_sanitize_str(partner_country),
                self._l10n_ae_faf_sanitize_str(line_vals['partner_vat']),
                self._l10n_ae_faf_sanitize_date(line_vals['date']),
                self._l10n_ae_faf_sanitize_str(move_vals['name']),
            )
            if line_type == 'purchase':
                line = (*line, self._l10n_ae_faf_sanitize_str(line_vals['l10n_ae_import_permit_number']))

            line = (*line,
                self._l10n_ae_faf_sanitize_int(move_vals['id']),
                self._l10n_ae_faf_sanitize_int(line_no),
                self._l10n_ae_faf_sanitize_str(line_vals['name']),
                self._l10n_ae_faf_sanitize_float(move_vals['sign'] * line_vals['balance']),
                self._l10n_ae_faf_sanitize_float(tax_amount),
                self._l10n_ae_faf_sanitize_str(l10n_ae_tax_code),
            )

            if line_type == 'sale':
                line = (
                    *line,
                    self._l10n_ae_faf_sanitize_str(line_vals['delivery_partner_state_name'] if line_vals['delivery_partner_country_code'] == 'AE' else line_vals['delivery_partner_country_name']),
                )

            line = (
                *line,
                self._l10n_ae_faf_sanitize_str(line_vals['currency_code']),
                self._l10n_ae_faf_sanitize_float(line_vals['price_subtotal']),
                self._l10n_ae_faf_sanitize_float(tax_amount_currency))

            lines_to_add.append(line)
            if line_type == 'purchase':
                running_totals['supplier_purchase_total'] += move_vals['sign'] * line_vals['balance']
                running_totals['supplier_purchase_vat'] += tax_amount
                running_totals['supplier_purchase_count'] += 1
            else:
                running_totals['customer_supply_total'] += move_vals['sign'] * line_vals['balance']
                running_totals['customer_supply_vat'] += tax_amount
                running_totals['customer_supply_count'] += 1

        lines.extend(lines_to_add)

    @api.model
    def _l10n_ae_faf_prepare_general_ledger_lines(self, move_vals, lines, running_totals):
        lines_to_add = []
        for line_vals in move_vals['lines'].values():
            source_type = self._l10n_ae_faf_get_general_ledger_line_source_type(line_vals)

            lines_to_add.append((
                self._l10n_ae_faf_sanitize_date(line_vals['date']),
                self._l10n_ae_faf_sanitize_str(line_vals['account_code']),
                self._l10n_ae_faf_sanitize_str(line_vals['account_name']),
                self._l10n_ae_faf_sanitize_str(move_vals['name']),
                self._l10n_ae_faf_sanitize_str(line_vals['partner_name']),
                self._l10n_ae_faf_sanitize_int(move_vals['id']),
                self._l10n_ae_faf_sanitize_str(line_vals['ref']),
                self._l10n_ae_faf_sanitize_str(source_type),
                self._l10n_ae_faf_sanitize_float(line_vals['debit']),
                self._l10n_ae_faf_sanitize_float(line_vals['credit']),
                self._l10n_ae_faf_sanitize_float(line_vals['balance']),
            ))

            running_totals['general_ledger_debit'] += line_vals['debit']
            running_totals['general_ledger_credit'] += line_vals['credit']
            running_totals['general_ledger_count'] += 1

        lines.extend(lines_to_add)

    @api.model
    def _l10n_ae_faf_get_general_ledger_line_source_type(self, line_vals):
        match line_vals['move_type']:
            case 'in_invoice':
                return 'Accounts Payable'
            case 'out_invoice':
                return 'Account Receivable'
            case 'out_refund':
                return 'AR - Cancel'
            case 'in_refund':
                return 'AP - Cancel'
            case _:
                return 'Cash Book Entries' if line_vals['account_type'] == 'asset_cash' else 'Journal Entries'
