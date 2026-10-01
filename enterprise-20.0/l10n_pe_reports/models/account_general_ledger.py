# coding: utf-8
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import csv
from io import StringIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import groupby, SQL
from odoo.tools.float_utils import float_repr
from odoo.addons.l10n_pe_reports.models.res_company import CHART_OF_ACCOUNTS


class AccountGeneralLedgerReportHandler(models.AbstractModel):
    _inherit = 'account.general.ledger.report.handler'

    def _custom_options_initializer(self, report, options, previous_options):
        # Overridden to add export button on GL for Peruvian companies
        super()._custom_options_initializer(report, options, previous_options=previous_options)

        if self.env.company.account_fiscal_country_id.code == "PE":
            options["buttons"].append({
                "name": _("PLE 5.1"),
                "sequence": 30,
                "action": "export_file",
                "action_param": "l10n_pe_export_ple_51_to_txt",
                "file_export_type": _("TXT"),
            })
            options["buttons"].append({
                "name": _("PLE 5.3"),
                "sequence": 35,
                "action": "export_file",
                "action_param": "l10n_pe_export_ple_53_to_txt",
                "file_export_type": _("TXT"),
            })
            options["buttons"].append({
                "name": _("PLE 6.1"),
                "sequence": 40,
                "action": "export_file",
                "action_param": "l10n_pe_export_ple_61_to_txt",
                "file_export_type": _("TXT"),
            })

    def _l10n_pe_get_file_txt(self, options, data, report_number):
        txt_result = ""
        if data:
            output = StringIO()
            writer = csv.DictWriter(output, delimiter="|", skipinitialspace=True, lineterminator='\n', fieldnames=[*data[0], object()])
            writer.writerows(data)
            txt_result = output.getvalue()

        # The name of the file is based on this link
        # http://orientacion.sunat.gob.pe/index.php/empresas-menu/libros-y-registros-vinculados-asuntos-tributarios-empresas/sistema-de-libros-electronicos-ple/6560-05-nomenclatura-de-libros-electronicos
        date_from = fields.Date.to_date(options["date"]["date_from"])
        has_data = "1" if data else "0"
        report_filename = "LE%s%s%02d00%s00001%s11" % (
            self.env.company.vat, date_from.year, date_from.month, report_number, has_data)

        return {
            "file_name": report_filename,
            "file_content": txt_result.encode(),
            "file_type": "txt",
        }

    @api.model
    def l10n_pe_export_ple_51_to_txt(self, options):
        txt_data = self._l10n_pe_get_txt_data(options, ple_version="ple_51")

        return self._l10n_pe_get_file_txt(options, txt_data, "0501")

    @api.model
    def l10n_pe_export_ple_53_to_txt(self, options):
        if self.env.company.account_fiscal_country_id.code != 'PE':
            raise UserError(_("Only Peruvian company can generate PLE 5.3 report."))

        txt_data = self._l10n_pe_get_txt_53_data(options)
        return self._l10n_pe_get_file_txt(options, txt_data, "0503")

    @api.model
    def l10n_pe_export_ple_61_to_txt(self, options):
        txt_data = self._l10n_pe_get_txt_data(options, ple_version="ple_61")
        return self._l10n_pe_get_file_txt(options, txt_data, "0601")

    def _l10n_pe_get_txt_data(self, options, ple_version=None):
        """ Generates the TXT content for the PLE reports with the entries data """
        def _get_ple_document_type(move_type, document_type, company_vat, partner_vat):
            if move_type in ("out_invoice", "out_refund") and document_type and company_vat:
                return company_vat.zfill(11)[:11]
            if move_type in ("in_invoice", "in_refund") and document_type and partner_vat:
                return partner_vat.zfill(11)[:11]
            return ""

        # Retrieve the data from the ledger itself, unfolding every group
        ledger = self.env['account.report'].browse(options['report_id'])
        # Options ---------------------------------
        # We don't need all companies
        options['companies'] = [{'name': self.env.company.name, 'id': self.env.company.id}]

        # Prepare query to get lines
        domain = ledger._get_options_domain(options, "strict_range")
        query = self.env['account.move.line']._search(domain)
        aml = query.table
        move = aml.move_id
        move_partner = move.partner_id
        query.order = SQL("%s, %s", aml.date, aml.id)
        qu = query.select(
            aml.id,
            aml.name,
            aml.date,
            aml.amount_currency,
            aml.debit,
            aml.credit,
            SQL("%s AS account_code", aml.account_id.code),
            move.l10n_pe_sunat_transaction_type,
            SQL("%s AS currency_name", aml.currency_id.name),
            move,
            SQL("%s AS move_date", move.date),
            SQL("%s AS move_name", move.name),
            SQL("%s AS move_date_due", move.invoice_date_due),
            SQL("%s AS move_invoice_date", move.invoice_date),
            SQL("%s AS move_type", move.move_type),
            SQL("%s AS document_type", move.l10n_latam_document_type_id.code),
            SQL("%s AS partner_vat", move_partner.vat),
            SQL("%s AS partner_document_type", move_partner.l10n_pe_sunat_id_code),
            SQL("%s AS country_code", move_partner.country_id.code),
        )
        lines_data = self.env.execute_query_dict(qu)

        data = []
        ple = self.env["l10n_pe.tax.ple.report.handler"]

        period = options["date"]["date_from"].replace("-", "")
        for _move_id, line_vals in groupby(lines_data, lambda line: line["move_id"]):
            for count, line in enumerate(line_vals, start=1):
                serie_folio = ple._get_serie_folio(line["move_name"]  or "")
                transaction_type = line["l10n_pe_sunat_transaction_type"]
                ple_journal_type = "M" if not transaction_type else ("A" if transaction_type == "opening" else "C" if transaction_type == "closing" else "")
                ple_document_type = _get_ple_document_type(line["move_type"], line["document_type"], self.env.company.vat, line["partner_vat"])

                data.append(
                    {
                        "period": "%s00" % period[:6],
                        "cuo": line["move_id"],
                        "number": "%s%s" % (ple_journal_type, count),
                        "account": line["account_code"],
                        "code": "",
                        "analytic": "",
                        "currency": line["currency_name"],
                        "partner_type": line["partner_document_type"] or "",
                        "partner_number": line["partner_vat"] or "",
                        "document_type": line["document_type"] if ple_document_type else "00",
                        "serie": serie_folio["serie"].replace(" ", "").replace("/", ""),
                        "folio": serie_folio["folio"].replace(" ", ""),
                        "date": line["date"].strftime("%d/%m/%Y") if line["move_date"] else "",
                        "due_date": line["move_date_due"].strftime("%d/%m/%Y") if line["move_date_due"] else "",
                        "invoice_date": (line["move_invoice_date"] or line["move_date"]).strftime("%d/%m/%Y") if line["move_invoice_date"] or line["date"] else "",
                        "glosa": line["move_name"],
                        "glosa_ref": "",
                        "debit": float_repr(line["debit"], precision_digits=2),
                        "credit": float_repr(line["credit"], precision_digits=2),
                        "book": "" if ple_version == "ple_61" else "%s%s%s%s" % (
                            ple_document_type,
                            line["document_type"].zfill(2)[-2:],
                            serie_folio["serie"].replace(" ", "").replace("/", "").zfill(4)[-4:],
                            serie_folio["folio"].replace(" ", "").zfill(10)[-10:]
                        ) if ple_document_type else "",
                        "state": "1",
                    }
                )
        return data

    def _l10n_pe_get_txt_53_data(self, options):
        accounts = self.env['account.account'].search([
            ('company_ids', '=', self.env.company.id),
            ('account_type', '!=', 'equity_unaffected'),
        ])

        data = []
        period = options["date"]["date_from"].replace("-", "")
        chart = self.env.company.l10n_pe_chart_of_accounts
        for account in accounts:
            data.append(
                {
                    "period": period[:8],
                    "code": account.code,
                    "name": account.name[:100],
                    "chart_account_code": (chart or "").zfill(2),
                    "chart_account_name": dict(CHART_OF_ACCOUNTS).get(chart, ""),
                    "corporative_account": "",
                    "corporative_account_name": "",
                    "state": "1",
                }
            )

        return data
