# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io
import re
import tempfile
import zipfile
from collections import namedtuple, defaultdict
from datetime import datetime

from odoo import fields, models, _
from odoo.tools import float_repr, split_every, float_compare
from odoo.tools.business_data import split_vat
from odoo.tools.constants import IN_MAX


BalanceKey = namedtuple('BalanceKey', ['from_code', 'to_code', 'partner_id', 'tax_id'])


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Add the invoice lines search domain that common for all countries.
        :param dict options: Report options
        :param dict previous_options: Previous report options
        """
        super()._custom_options_initializer(report, options, previous_options)
        if self.env.company.country_code in ('DE', 'CH', 'AT'):
            options.setdefault('buttons', []).extend((
                {
                    'name': _('Datev DATA (zip)'),
                    'sequence': 30,
                    'action': 'export_file',
                    'action_param': 'l10n_de_datev_export_to_zip',
                    'file_export_type': _('Datev zip'),
                },
                {
                    'name': _('Datev ATCH (zip)'),
                    'sequence': 40,
                    'action': 'export_file',
                    'action_param': 'l10_de_datev_export_to_zip_and_attach',
                    'file_export_type': _('Datev + batch zip'),
                },
            ))

    def _l10n_de_datev_build_line(
        self,
        *,
        line_amount_currency,
        line_amount,
        currency,
        company_currency,
        account_code,
        counterpart_code,
        code_correction,
        move,
        receipt1,
        receipt2,
        reference_text,
        force_debit_credit=None,
    ):
        """
        Build and return a 125-field DATEV export row.
        """
        # Idiotic program needs to have a line with 125 elements ordered in a given fashion as it
        # does not take into account the header and non mandatory fields
        array = ['' for _ in range(125)]
        # For DateV, we can't have negative amount on a line, so we need to inverse the amount and inverse the
        # credit/debit symbol.
        if force_debit_credit:
            array[1] = force_debit_credit
        else:
            array[1] = 'H' if currency.compare_amounts(line_amount, 0) < 0 else 'S'
        line_amount = abs(line_amount)
        # Column A: the amount in the currency that was used. It can be a foreign one, it can be the company's.
        array[0] = float_repr(line_amount_currency, currency.decimal_places).replace('.', ',')
        # Column C: the corresponding foreign currency used on the original record (invoice, bill, entry, ....)
        array[2] = currency.name
        if currency != company_currency:
            # Column D: ratio is E/A if D !=0, else no rate.
            if not company_currency.is_zero(line_amount) and not currency.is_zero(line_amount_currency):
                rate = round(line_amount_currency / line_amount, 6) or 1.0
            else:
                rate = 1.0
            array[3] = str(rate).replace('.', ',')
            # Column E: the amount converted in the company currency if the original record was in a foreign currency
            array[4] = float_repr(line_amount, company_currency.decimal_places).replace('.', ',')
            # Column F: the company currency if the original record was in a foreign currency
            array[5] = company_currency.name
        array[6] = account_code
        array[7] = counterpart_code
        array[8] = code_correction
        array[9] = datetime.strftime(move.date, '%-d%m')
        array[10] = receipt1[-36:]
        array[11] = receipt2
        array[13] = reference_text or ''
        if move.message_main_attachment_id:
            array[19] = f'BEDI "{move._l10n_de_datev_get_guid()}"'

        return array

    def l10_de_datev_export_to_zip_and_attach(self, options):
        options['add_attachments'] = True
        return self.l10n_de_datev_export_to_zip(options)

    def l10n_de_datev_export_to_zip(self, options):
        """
        Check ir_attachment for method _get_path
        create a sha and replace 2 first letters by something not hexadecimal
        Return full_path as 2nd args, use it as name for Zipfile
        Don't need to unlink as it will be done automatically by garbage collector
        of attachment cron
        """
        report = self.env['account.report'].browse(options['report_id'])
        with tempfile.NamedTemporaryFile(mode='w+b', delete=True) as buf:
            with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED, allowZip64=False) as zf:
                domain = report._get_options_domain(options, 'strict_range')
                move_line_ids = self.env['account.move.line'].search(domain).ids

                domain = [
                    ('line_ids', 'in', move_line_ids),
                    ('company_id', 'in', report.get_report_company_ids(options)),
                    ('date', '<=', options['date']['date_to']),
                ]
                if options.get('all_entries'):
                    domain += [('state', '!=', 'cancel')]
                else:
                    domain += [('state', '=', 'posted')]

                    # cannot set date_from on move as domain depends on the move line account if "strict_range" is False
                domain += report._get_options_journals_domain(options)
                moves = self.env['account.move'].search(domain)
                if options.get('add_attachments'):
                    # add all moves attachments in zip file
                    slash_re = re.compile('[\\/]')
                    documents = []
                    moves.fetch(['id', 'name', 'move_type', 'message_main_attachment_id'])
                    for move in moves.filtered(lambda m: m.message_main_attachment_id):
                        # The message_main_attachment_id may not be linked to the associated move causing AccessError
                        # For example, with an image, the res_id is 0 and the res_model is False
                        attachment = move.sudo().message_main_attachment_id
                        base_name = slash_re.sub('-', move.name)
                        extension = attachment.name.split('.')[-1]
                        name = f"{base_name}.{extension}"
                        zf.writestr(name, attachment.raw.content)
                        documents.append({
                            'guid': move._l10n_de_datev_get_guid(),
                            'filename': name,
                            'type': 2 if move.is_sale_document() else 1 if move.is_purchase_document() else None,
                        })
                    if documents:
                        metadata_document = self.env['ir.qweb']._render(
                            'l10n_de_reports.datev_export_metadata',
                            values={
                                'documents': documents,
                                'date': fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                            },
                        )
                        zf.writestr('document.xml', "<?xml version='1.0' encoding='UTF-8'?>" + str(metadata_document))
                else:
                    # ZIP for Data => csv
                    set_move_line_ids = set(move_line_ids)
                    zf.writestr('EXTF_accounting_entries.csv', self._l10n_de_datev_get_csv(options, moves))
                    zf.writestr('EXTF_customer_accounts.csv', self._l10n_de_datev_get_partner_list(options, set_move_line_ids, customer=True))
                    zf.writestr('EXTF_vendor_accounts.csv', self._l10n_de_datev_get_partner_list(options, set_move_line_ids, customer=False))
            buf.seek(0)
            content = buf.read()

        filename, extension = report.get_default_report_filename(options, 'ZIP').rsplit('.', 1)
        return {
            'file_name': f'{filename}_atch.{extension}' if options.get('add_attachments') else f'{filename}_data.{extension}',
            'file_content': content,
            'file_type': 'zip'
        }

    def _l10n_de_datev_get_client_number(self):
        consultant_number = self.env.company.l10n_de_datev_consultant_number
        client_number = self.env.company.l10n_de_datev_client_number
        if not consultant_number:
            consultant_number = 99999
        if not client_number:
            client_number = 999
        return [consultant_number, client_number]

    def _l10n_de_datev_get_partner_list(self, options, move_line_ids, customer=True):
        date_to = fields.Date.to_date(options['date']['date_to'])
        fy = self.env.company.compute_fiscalyear_dates(date_to)

        fy = datetime.strftime(fy['date_from'], '%Y%m%d')
        datev_info = self._l10n_de_datev_get_client_number()
        account_length = self._l10n_de_datev_get_account_length()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=2)
        preheader = ['EXTF', 700, 16, 'Debitoren/Kreditoren', 5, None, None, '', '', '', datev_info[0], datev_info[1], fy, account_length,
            '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '', '']
        header = [
            'Konto', 'Name (Adressattyp Unternehmen)', 'Unternehmensgegenstand', 'Name (Adressattyp natürl. Person)',
            'Vorname (Adressattyp natürl. Person)', 'Name (Adressattyp keine Angabe)', 'Adressattyp', 'Kurzbezeichnung',
            'EU-Land', 'EU-UStID', 'Anrede', 'Titel/Akad. Grad', 'Adelstitel', 'Namensvorsatz', 'Adressart', 'Straße',
            'Postfach', 'Postleitzahl', 'Ort', 'Land', 'Versandzusatz', 'Adresszusatz', 'Abweichende Anrede', 'Abw. Zustellbezeichnung 1',
            'Abw. Zustellbezeichnung 2', 'Kennz. Korrespondenzadresse', 'Adresse Gültig von', 'Adresse Gültig bis', 'Telefon',
            'Bemerkung (Telefon)', 'Telefon GL', 'Bemerkung (Telefon GL)', 'E-Mail', 'Bemerkung (E-Mail)', 'Internet',
            'Bemerkung (Internet)', 'Fax', 'Bemerkung (Fax)', 'Sonstige', 'Bemerkung (Sonstige)', 'Bankleitzahl 1',
            'Bankbezeichnung 1', 'Bank-Kontonummer 1', 'Länderkennzeichen 1', 'IBAN-Nr. 1', 'Leerfeld', 'SWIFT-Code 1',
            'Abw. Kontoinhaber 1', 'Kennz. Hauptbankverb. 1', 'Bankverb 1 Gültig von', 'Bankverb 1 Gültig bis', 'Bankleitzahl 2',
            'Bankbezeichnung 2', 'Bank-Kontonummer 2', 'Länderkennzeichen 2', 'IBAN-Nr. 2', 'Leerfeld', 'SWIFT-Code 2',
            'Abw. Kontoinhaber 2', 'Kennz. Hauptbankverb. 2', 'Bankverb 2 Gültig von', 'Bankverb 2 Gültig bis', 'Bankleitzahl 3',
            'Bankbezeichnung 3', 'Bank-Kontonummer 3', 'Länderkennzeichen 3', 'IBAN-Nr. 3', 'Leerfeld', 'SWIFT-Code 3',
            'Abw. Kontoinhaber 3', 'Kennz. Hauptbankverb. 3', 'Bankverb 3 Gültig von', 'Bankverb 3 Gültig bis', 'Bankleitzahl 4',
            'Bankbezeichnung 4', 'Bank-Kontonummer 4', 'Länderkennzeichen 4', 'IBAN-Nr. 4', 'Leerfeld', 'SWIFT-Code 4',
            'Abw. Kontoinhaber 4', 'Kennz. Hauptbankverb. 4', 'Bankverb 4 Gültig von', 'Bankverb 4 Gültig bis', 'Bankleitzahl 5',
            'Bankbezeichnung 5', 'Bank-Kontonummer 5', 'Länderkennzeichen 5', 'IBAN-Nr. 5', 'Leerfeld', 'SWIFT-Code 5',
            'Abw. Kontoinhaber 5', 'Kennz. Hauptbankverb. 5', 'Bankverb 5 Gültig von', 'Bankverb 5 Gültig bis', 'Leerfeld',
            'Briefanrede', 'Grußformel', 'Kunden-/Lief.-Nr.', 'Steuernummer', 'Sprache', 'Ansprechpartner', 'Vertreter',
            'Sachbearbeiter', 'Diverse-Konto', 'Ausgabeziel', 'Währungssteuerung', 'Kreditlimit (Debitor)', 'Zahlungsbedingung',
            'Fälligkeit in Tagen (Debitor)', 'Skonto in Prozent (Debitor)', 'Kreditoren-Ziel 1 Tg.', 'Kreditoren-Skonto 1 %',
            'Kreditoren-Ziel 2 Tg.', 'Kreditoren-Skonto 2 %', 'Kreditoren-Ziel 3 Brutto Tg.', 'Kreditoren-Ziel 4 Tg.',
            'Kreditoren-Skonto 4 %', 'Kreditoren-Ziel 5 Tg.', 'Kreditoren-Skonto 5 %', 'Mahnung', 'Kontoauszug', 'Mahntext 1',
            'Mahntext 2', 'Mahntext 3', 'Kontoauszugstext', 'Mahnlimit Betrag', 'Mahnlimit %', 'Zinsberechnung', 'Mahnzinssatz 1',
            'Mahnzinssatz 2', 'Mahnzinssatz 3', 'Lastschrift', 'Leerfeld', 'Mandantenbank', 'Zahlungsträger', 'Indiv. Feld 1',
            'Indiv. Feld 2', 'Indiv. Feld 3', 'Indiv. Feld 4', 'Indiv. Feld 5', 'Indiv. Feld 6', 'Indiv. Feld 7', 'Indiv. Feld 8',
            'Indiv. Feld 9', 'Indiv. Feld 10', 'Indiv. Feld 11', 'Indiv. Feld 12', 'Indiv. Feld 13', 'Indiv. Feld 14',
            'Indiv. Feld 15', 'Abweichende Anrede (Rechnungsadresse)', 'Adressart (Rechnungsadresse)', 'Straße (Rechnungsadresse)',
            'Postfach (Rechnungsadresse)', 'Postleitzahl (Rechnungsadresse)', 'Ort (Rechnungsadresse)', 'Land (Rechnungsadresse)',
            'Versandzusatz (Rechnungsadresse)', 'Adresszusatz (Rechnungsadresse)', 'Abw. Zustellbezeichnung 1 (Rechnungsadresse)',
            'Abw. Zustellbezeichnung 2 (Rechnungsadresse)', 'Adresse Gültig von (Rechnungsadresse)', 'Adresse Gültig bis (Rechnungsadresse)',
            'Bankleitzahl 6', 'Bankbezeichnung 6', 'Bank-Kontonummer 6', 'Länderkennzeichen 6', 'IBAN-Nr. 6', 'Leerfeld',
            'SWIFT-Code 6', 'Abw. Kontoinhaber 6', 'Kennz. Hauptbankverb. 6', 'Bankverb 6 Gültig von', 'Bankverb 6 Gültig bis',
            'Bankleitzahl 7', 'Bankbezeichnung 7', 'Bank-Kontonummer 7', 'Länderkennzeichen 7', 'IBAN-Nr. 7', 'Leerfeld',
            'SWIFT-Code 7', 'Abw. Kontoinhaber 7', 'Kennz. Hauptbankverb. 7', 'Bankverb 7 Gültig von', 'Bankverb 7 Gültig bis',
            'Bankleitzahl 8', 'Bankbezeichnung 8', 'Bank-Kontonummer 8', 'Länderkennzeichen 8', 'IBAN-Nr. 8', 'Leerfeld',
            'SWIFT-Code 8', 'Abw. Kontoinhaber 8', 'Kennz. Hauptbankverb. 8', 'Bankverb 8 Gültig von', 'Bankverb 8 Gültig bis',
            'Bankleitzahl 9', 'Bankbezeichnung 9', 'Bank-Kontonummer 9', 'Länderkennzeichen 9', 'IBAN-Nr. 9', 'Leerfeld',
            'SWIFT-Code 9', 'Abw. Kontoinhaber 9', 'Kennz. Hauptbankverb. 9', 'Bankverb 9 Gültig von', 'Bankverb 9 Gültig bis',
            'Bankleitzahl 10', 'Bankbezeichnung 10', 'Bank-Kontonummer 10', 'Länderkennzeichen 10', 'IBAN-Nr. 10', 'Leerfeld',
            'SWIFT-Code 10', 'Abw. Kontoinhaber 10', 'Kennz. Hauptbankverb. 10', 'Bankverb 10 Gültig von', 'Bankverb 10 Gültig bis',
            'Nummer Fremdsystem', 'Insolvent', 'SEPA-Mandatsreferenz 1', 'SEPA-Mandatsreferenz 2', 'SEPA-Mandatsreferenz 3',
            'SEPA-Mandatsreferenz 4', 'SEPA-Mandatsreferenz 5', 'SEPA-Mandatsreferenz 6', 'SEPA-Mandatsreferenz 7',
            'SEPA-Mandatsreferenz 8', 'SEPA-Mandatsreferenz 9', 'SEPA-Mandatsreferenz 10', 'Verknüpftes OPOS-Konto',
            'Mahnsperre bis', 'Lastschriftsperre bis', 'Zahlungssperre bis', 'Gebührenberechnung', 'Mahngebühr 1', 'Mahngebühr 2',
            'Mahngebühr 3', 'Pauschalenberechnung', 'Verzugspauschale 1', 'Verzugspauschale 2', 'Verzugspauschale 3',
            'Alternativer Suchname', 'Status', 'Anschrift manuell geändert (Korrespondenzadresse)', 'Anschrift individuell (Korrespondenzadresse)',
            'Anschrift manuell geändert (Rechnungsadresse)', 'Anschrift individuell (Rechnungsadresse)', 'Fristberechnung bei Debitor',
            'Mahnfrist 1', 'Mahnfrist 2', 'Mahnfrist 3', 'Letzte Frist',
        ]

        lines = [preheader, header]

        if len(move_line_ids):
            if customer:
                move_types = ('out_refund', 'out_invoice', 'out_receipt')
            else:
                move_types = ('in_refund', 'in_invoice', 'in_receipt')
            select = """SELECT distinct(aml.partner_id)
                        FROM account_move_line aml
                        JOIN account_move m
                        ON aml.move_id = m.id
                        WHERE aml.id IN %s
                            AND aml.tax_line_id IS NULL
                            AND aml.debit != aml.credit
                            AND m.move_type IN %s
                            AND aml.account_id != m.l10n_de_datev_main_account_id
                            AND aml.partner_id IS NOT NULL"""
            self.env.cr.execute(select, (tuple(move_line_ids), move_types))
        partners = self.env['res.partner'].browse([p.get('partner_id') for p in self.env.cr.dictfetchall()])
        eu_country_codes = self.env.ref('base.europe').country_ids.mapped('code')
        for partner in partners:
            if customer:
                code = self._l10n_de_datev_find_partner_account(partner.property_account_receivable_id, partner)
            else:
                code = self._l10n_de_datev_find_partner_account(partner.property_account_payable_id, partner)
            vat_is_valid = False

            country_code = ''
            if partner.has_vat:
                vat_country, vat_id_no = split_vat(partner.vat)
                vat_is_valid = vat_country and partner._check_vat_number(vat_country, vat_id_no)
                if vat_country.isalpha():
                    country_code = 'GR' if vat_country.upper() == 'EL' else vat_country.upper()
            is_eu_vat_number = country_code in eu_country_codes

            line_value = {
                'code': code,
                'company_name': partner.name if partner.is_company else '',
                'person_name': '' if partner.is_company else partner.name,
                'natural': partner.is_company and '2' or '1',
                'eu_vat_country': vat_country.upper() if vat_is_valid and is_eu_vat_number and vat_country.isalpha() else '',
                'eu_vat_id_no': vat_id_no if vat_is_valid and is_eu_vat_number else '',
                'country_code': partner.country_code or country_code or '',
            }
            # Idiotic program needs to have a line with 243 elements ordered in a given fashion as it
            # does not take into account the header and non mandatory fields
            array = ['' for x in range(243)]
            array[0] = line_value.get('code')
            array[1] = line_value.get('company_name')
            array[3] = line_value.get('person_name')
            array[6] = line_value.get('natural')
            array[8] = line_value.get('eu_vat_country')
            array[9] = line_value.get('eu_vat_id_no')
            array[19] = line_value.get('country_code')
            lines.append(array)
        writer.writerows(lines)
        return output.getvalue()

    def _l10n_de_datev_get_account_length(self):
        return self.env.company.l10n_de_datev_account_length

    def _l10n_de_datev_find_partner_account(self, account, partner):
        len_param = self._l10n_de_datev_get_account_length()
        if partner:
            if account.account_type == 'asset_receivable':
                return str(partner.l10n_de_datev_identifier_customer or 10 ** len_param + partner.id)
            if account.account_type == 'liability_payable':
                return str(partner.l10n_de_datev_identifier or 7 * 10 ** len_param + partner.id)
        return str(account.code).ljust(len_param, '0') if account else ''

    # Source: http://www.datev.de/dnlexom/client/app/index.html#/document/1036228/D103622800029
    def _l10n_de_datev_get_csv(self, options, moves):
        # last 2 element of preheader should be filled by "consultant number" and "client number"
        date_from = fields.Date.to_date(options['date']['date_from'])
        date_to = fields.Date.to_date(options['date']['date_to'])
        fy = self.env.company.compute_fiscalyear_dates(date_to)

        date_from = datetime.strftime(date_from, '%Y%m%d')
        date_to = datetime.strftime(date_to, '%Y%m%d')
        fy = datetime.strftime(fy.get('date_from'), '%Y%m%d')
        datev_info = self._l10n_de_datev_get_client_number()
        account_length = self._l10n_de_datev_get_account_length()

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=2)
        preheader = ['EXTF', 700, 21, 'Buchungsstapel', 13, '', '', '', '', '', datev_info[0], datev_info[1], fy, account_length,
            date_from, date_to, '', '', '', '', 0, 'EUR', '', '', '', '', '', '', '', '', '']
        header = [
            'Umsatz (ohne Soll/Haben-Kz)', 'Soll/Haben-Kennzeichen', 'WKZ Umsatz', 'Kurs', 'Basis-Umsatz', 'WKZ Basis-Umsatz',
            'Konto', 'Gegenkonto (ohne BU-Schlüssel)', 'BU-Schlüssel', 'Belegdatum', 'Belegfeld 1', 'Belegfeld 2', 'Skonto',
            'Buchungstext', 'Postensperre', 'Diverse Adressnummer', 'Geschäftspartnerbank', 'Sachverhalt', 'Zinssperre',
            'Beleglink', 'Beleginfo - Art 1', 'Beleginfo - Inhalt 1', 'Beleginfo - Art 2', 'Beleginfo - Inhalt 2',
            'Beleginfo - Art 3', 'Beleginfo - Inhalt 3', 'Beleginfo - Art 4', 'Beleginfo - Inhalt 4',
            'Beleginfo - Art 5', 'Beleginfo - Inhalt 5', 'Beleginfo - Art 6', 'Beleginfo - Inhalt 6',
            'Beleginfo - Art 7', 'Beleginfo - Inhalt 7', 'Beleginfo - Art 8', 'Beleginfo - Inhalt 8', 'KOST1 - Kostenstelle',
            'KOST2 - Kostenstelle', 'Kost-Menge', 'EU-Land u. UStID (Bestimmung)', 'EU-Steuersatz (Bestimmung)',
            'Abw. Versteuerungsart', 'Sachverhalt L+L', 'Funktionsergänzung L+L', 'BU 49 Hauptfunktionstyp', 'BU 49 Hauptfunktionsnummer',
            'BU 49 Funktionsergänzung', 'Zusatzinformation - Art 1', 'Zusatzinformation- Inhalt 1', 'Zusatzinformation - Art 2',
            'Zusatzinformation- Inhalt 2', 'Zusatzinformation - Art 3', 'Zusatzinformation- Inhalt 3', 'Zusatzinformation - Art 4',
            'Zusatzinformation- Inhalt 4', 'Zusatzinformation - Art 5', 'Zusatzinformation- Inhalt 5', 'Zusatzinformation - Art 6',
            'Zusatzinformation- Inhalt 6', 'Zusatzinformation - Art 7', 'Zusatzinformation- Inhalt 7', 'Zusatzinformation - Art 8',
            'Zusatzinformation- Inhalt 8', 'Zusatzinformation - Art 9', 'Zusatzinformation- Inhalt 9', 'Zusatzinformation - Art 10',
            'Zusatzinformation- Inhalt 10', 'Zusatzinformation - Art 11', 'Zusatzinformation- Inhalt 11', 'Zusatzinformation - Art 12',
            'Zusatzinformation- Inhalt 12', 'Zusatzinformation - Art 13', 'Zusatzinformation- Inhalt 13', 'Zusatzinformation - Art 14',
            'Zusatzinformation- Inhalt 14', 'Zusatzinformation - Art 15', 'Zusatzinformation- Inhalt 15', 'Zusatzinformation - Art 16',
            'Zusatzinformation- Inhalt 16', 'Zusatzinformation - Art 17', 'Zusatzinformation- Inhalt 17', 'Zusatzinformation - Art 18',
            'Zusatzinformation- Inhalt 18', 'Zusatzinformation - Art 19', 'Zusatzinformation- Inhalt 19', 'Zusatzinformation - Art 20',
            'Zusatzinformation- Inhalt 20', 'Stück', 'Gewicht', 'Zahlweise', 'Forderungsart', 'Veranlagungsjahr', 'Zugeordnete Fälligkeit',
            'Skontotyp', 'Auftragsnummer', 'Buchungstyp', 'USt-Schlüssel (Anzahlungen)', 'EU-Land (Anzahlungen)', 'Sachverhalt L+L (Anzahlungen)',
            'EU-Steuersatz (Anzahlungen)', 'Erlöskonto (Anzahlungen)', 'Herkunft-Kz', 'Buchungs GUID', 'KOST-Datum', 'SEPA-Mandatsreferenz',
            'Skontosperre', 'Gesellschaftername', 'Beteiligtennummer', 'Identifikationsnummer', 'Zeichnernummer', 'Postensperre bis',
            'Bezeichnung SoBil-Sachverhalt', 'Kennzeichen SoBil-Buchung', 'Festschreibung', 'Leistungsdatum', 'Datum Zuord. Steuerperiode',
            'Fälligkeit', 'Generalumkehr (GU)', 'Steuersatz', 'Land', 'Abrechnungsreferenz', 'BVV-Position', 'EU-Land u. UStID (Ursprung)',
            'EU-Steuersatz (Ursprung)', 'Abw. Skontokonto',
        ]

        writer.writerows([preheader, header])
        for batch in split_every(IN_MAX, moves.ids, moves.browse):
            self._fetch_used_cols_only(batch)
            writer.writerows(self._get_report_lines(batch))
            batch.line_ids.invalidate_recordset()
            batch.invalidate_recordset()
        return output.getvalue()

    def _fetch_used_cols_only(self, batch):
        batch.fetch(['id', 'move_type', 'name', 'ref', 'date', 'journal_id', 'message_main_attachment_id', 'origin_payment_id', 'statement_line_id', 'company_id', 'l10n_de_datev_main_account_id'])
        batch.line_ids.fetch(['id', 'name', 'debit', 'credit', 'payment_id', 'balance', 'statement_line_id', 'account_id', 'tax_line_id', 'price_total', 'currency_id', 'company_id', 'date', 'date_maturity', 'amount_currency', 'partner_id'])

    def _get_report_lines(self, moves):
        lines = []
        for m in moves:
            delta_by_aml = defaultdict(float)    # the final delta to apply to each aml
            # For bills, it's possible to edit the total amount of a tax group manually.
            # Unfortunatly this change only affects the amounts in tax_totals field, but not
            # price_total field of the invoice lines, which is used in the export.
            # Therefore, the exported amount can be wrong because it doesn't include the tax change.
            # To detect such a case, we check if the sum of price_total of each line is equal to
            # the total amount in tax_totals.
            # It can happen that price_total is not set. In this case, the exported amount is
            # recomputed and also differs from the edited amount.
            # However, this case is not handled here for the moment.
            if (m.move_type == 'in_invoice' and
                all(line.price_total for line in m.invoice_line_ids) and
                float_compare(
                    m.tax_totals['total_amount'],
                    sum(m.invoice_line_ids.mapped('price_total')),
                    precision_rounding=m.currency_id.rounding,
                )
            ):
                # The amount of a tax group has probably been edited manually.
                # So we cannot use price_total of the aml as it is and we should dispatch the
                # delta between all the lines where a tax of the same group has been used.
                amls_by_group = defaultdict(list)
                # Get the modified tax group amounts
                actual_values_by_group = {
                    self.env['account.tax.group'].browse(tax_group['id']): tax_group['tax_amount_currency']
                    for subtotal in m.tax_totals['subtotals']
                    for tax_group in subtotal['tax_groups']
                }
                # Get the originally computed values
                original_values_by_group = defaultdict(float)
                for line in m.invoice_line_ids:
                    line_taxes = line.tax_ids.compute_all(line.amount_currency, line.currency_id, partner=line.partner_id, handle_price_include=False)
                    tax_amounts = defaultdict(float)
                    for tax_data in line_taxes['taxes']:
                        tax_amounts[tax_data['id']] += tax_data['amount']
                    for tax_id in tax_amounts:
                        tax = self.env['account.tax'].browse(tax_id)
                        original_values_by_group[tax.tax_group_id] += tax_amounts[tax.id]
                        amls_by_group[tax.tax_group_id].append(line)
                # Compute deltas by tax group and assign the difference
                for tax_group, actual_group_amount in actual_values_by_group.items():
                    delta_group_amount = actual_group_amount - original_values_by_group[tax_group]
                    current_lines = amls_by_group[tax_group]
                    nb_lines = len(current_lines)
                    # Round and add to every line
                    line_delta_amount = line.currency_id.round(delta_group_amount / nb_lines)
                    for line in current_lines:
                        delta_by_aml[line] += line_delta_amount
                    # Add eventual rounding remainder to the first line of the tax group
                    remainder = line.currency_id.round(delta_group_amount - line_delta_amount * nb_lines)
                    delta_by_aml[current_lines[0]] += remainder

            payment_account = 0  # Used for non-reconciled payments

            move_balance = 0
            counterpart_amount = 0
            last_tax_line_index = 0

            # Check for three currency case
            # A three-currency case occurs when a bank transaction involves:
            # - the payer's transaction currency,
            # - the bank journal's currency,
            # - the company's currency.
            # DATEV cannot represent both foreign currencies on the same journal item,
            # so foreign AR/AP lines are routed through a clearing account.
            clearing_account = ''
            foreign_arap_lines = self.env['account.move.line']
            emit_bank_line = True
            if m.statement_line_id:
                liquidity_lines, _, other_lines = m.statement_line_id._seek_for_lines()
                if len(liquidity_lines) == 1:
                    foreign_arap_lines = other_lines.filtered(
                        lambda aml: (
                            aml.account_id.account_type in (
                                'asset_receivable',
                                'liability_payable',
                            )
                            and not aml.is_same_currency
                            and aml.currency_id != liquidity_lines[0].currency_id
                        )
                    )
                    if foreign_arap_lines:
                        account_length = self._l10n_de_datev_get_account_length()
                        clearing_base = (
                            "1460"
                            if m.company_id.chart_template == "de_skr04"
                            else "1360"
                        )
                        clearing_account = clearing_base.ljust(account_length, '0')

            def _get_code_correction(taxes):
                codes = set(taxes.mapped('l10n_de_datev_code'))
                # there should be exactly one, else skip code
                return len(codes) == 1 and codes.pop() or ''

            for aml in m.line_ids:
                code_correction = ''
                if aml.debit == aml.credit:
                    # Ignore debit = credit = 0
                    continue

                # account and counterpart account
                to_account_code = f'{self._l10n_de_datev_find_partner_account(m.l10n_de_datev_main_account_id, aml.partner_id)}'
                account_code = f'{self._l10n_de_datev_find_partner_account(aml.account_id, aml.partner_id)}'

                # We don't want to have lines with our outstanding payment/receipt as they don't represent real moves
                # So if payment skip one move line to write, while keeping the account
                # and replace bank account for outstanding payment/receipt for the other line

                if aml.payment_id:
                    # An expense may be encoded with a tax, we should report the corresponding tax code
                    if not code_correction:
                        code_correction = _get_code_correction(m.line_ids.tax_ids)
                    if payment_account == 0:
                        payment_account = account_code
                        counterpart_amount += aml.balance
                        continue
                    to_account_code = payment_account

                # If both account and counteraccount are the same, ignore the line
                if aml.account_id == m.l10n_de_datev_main_account_id:
                    if aml.statement_line_id and not aml.payment_id:
                        counterpart_amount += aml.balance
                    continue

                # If line is a tax ignore it as datev requires single line with gross amount and deduct tax itself based
                # on account or on the control key code
                if aml.tax_line_id:
                    continue

                if aml.price_total and m.move_type != 'entry':
                    sign = -1 if aml.currency_id.compare_amounts(aml.balance, 0) < 0 else 1
                    line_amount_currency = abs(aml.price_total) * sign
                else:
                    aml_taxes = aml.tax_ids.compute_all(aml.amount_currency, aml.currency_id, partner=aml.partner_id, handle_price_include=False)
                    line_amount_currency = aml_taxes['total_included']
                # convert line_amount in company currency
                if aml.currency_id != aml.company_id.currency_id:
                    if not aml.currency_id.is_zero(line_amount_currency):
                        rate = m._get_product_base_line_currency_rate(aml)
                        line_amount = line_amount_currency / rate
                    else:
                        line_amount = aml.balance
                else:
                    line_amount = line_amount_currency

                move_balance += line_amount

                if aml.tax_ids:
                    last_tax_line_index = len(lines)
                    last_tax_line_amount = line_amount
                    code_correction = _get_code_correction(aml.tax_ids)

                # reference
                receipt1 = ref = m.name
                if m.journal_id.type == 'purchase' and m.ref:
                    ref = m.ref

                # on receivable/payable aml of sales/purchases
                receipt2 = ''
                if to_account_code == account_code and aml.date_maturity:
                    receipt2 = aml.date

                if aml in foreign_arap_lines:
                    if emit_bank_line:
                        lines.append(
                            self._l10n_de_datev_build_clearing_liquidity_line(
                                m,
                                liquidity_lines[0],
                                clearing_account,
                                foreign_arap_lines,
                            )
                        )
                        emit_bank_line = False

                    to_account_code = clearing_account

                lines.append(
                    self._l10n_de_datev_build_line(
                        line_amount_currency=abs(line_amount_currency) + delta_by_aml[aml],
                        line_amount=line_amount,
                        currency=aml.currency_id,
                        company_currency=aml.company_id.currency_id,
                        account_code=account_code,
                        counterpart_code=to_account_code,
                        code_correction=code_correction,
                        move=m,
                        receipt1=receipt1,
                        receipt2=receipt2,
                        reference_text=aml.name or ref,
                    )
                )
            # In case of epd we actively fix rounding issues by checking the base line and tax line
            # amounts against the move amount missing cent and adjust the vals accordingly.
            # Since here we have to recompute the tax values for each line with tax, we need
            # to replicate the rounding fix logic adding the difference on the last tax line
            # to avoid creating a difference with the source payment move
            if (m.origin_payment_id or m.statement_line_id) and move_balance and counterpart_amount and last_tax_line_index:
                delta_balance = move_balance + counterpart_amount
                if delta_balance:
                    lines[last_tax_line_index][0] = float_repr(abs(last_tax_line_amount - delta_balance), m.company_id.currency_id.decimal_places).replace('.', ',')
        return lines

    def _l10n_de_datev_build_clearing_liquidity_line(self, move, liquidity_line, clearing_account, foreign_arap_lines):
        """
        Build the liquidity leg through the clearing account, using the combined balance of the foreign AR/AP lines.
        """
        company_currency = move.company_id.currency_id
        liquidity_account_code = str(
            self._l10n_de_datev_find_partner_account(
                liquidity_line.account_id,
                liquidity_line.partner_id,
            )
        )
        liq_sh = "S" if company_currency.compare_amounts(liquidity_line.balance, 0.0) > 0 else "H"
        clearing_balance = sum(foreign_arap_lines.mapped('balance'))
        return self._l10n_de_datev_build_line(
            line_amount_currency=abs(liquidity_line.amount_currency),
            line_amount=clearing_balance,
            currency=liquidity_line.currency_id,
            company_currency=company_currency,
            account_code=liquidity_account_code,
            counterpart_code=clearing_account,
            code_correction='',
            move=move,
            receipt1=move.name,
            receipt2='',
            reference_text=liquidity_line.name or liquidity_line.ref,
            force_debit_credit=liq_sh,
        )
