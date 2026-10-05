import logging

from collections import defaultdict
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models, modules
from odoo.exceptions import RedirectWarning, UserError
from odoo.tools import exception_to_unicode

from odoo.addons.base.models.res_partner_bank import sanitize_account_number
from odoo.addons.l10n_be_codaclean.tools.iap_api import get_error_message, contact

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def _get_bank_statements_available_sources(self):
        # Extends 'account'
        rslt = super()._get_bank_statements_available_sources()
        rslt.append(("l10n_be_codaclean", _("Codaclean Synchronization")))
        return rslt

    def _fill_bank_cash_dashboard_data(self, dashboard_data):
        super()._fill_bank_cash_dashboard_data(dashboard_data)
        for journal_id in dashboard_data:
            journal = self.browse(journal_id)
            dashboard_data[journal_id]["l10n_be_codaclean_is_connected"] = journal.company_id.l10n_be_codaclean_is_connected
            dashboard_data[journal_id]["l10n_be_codaclean_journal_is_soda"] = journal == journal.company_id.l10n_be_codaclean_soda_journal
            if journal == journal.company_id.l10n_be_codaclean_soda_journal:
                dashboard_data[journal_id]["l10n_be_codaclean_number_draft"] = self.env['account.move'].search_count([
                    ('journal_id', '=', journal.id),
                    ('state', '=', 'draft'),
                ])

    def _l10n_be_codaclean_fetch_sodas_from_iap(self, date_from=None):
        self.company_id._l10n_be_codaclean_verify_prerequisites()
        if not date_from:
            date_from = fields.Date.to_string(fields.Date.today() - relativedelta(years=1))

        params = {
            "iap_token": self.company_id.sudo().l10n_be_codaclean_iap_token,
            "enterprise_number": self.company_id._l10n_be_codaclean_get_formatted_vat(),
            "from_date": date_from,
        }
        result = contact(self.env, "get_soda_files", params, timeout=(10, 900))
        if result.get("error", {}).get("type") == "iap_error_connection_not_found":
            self.company_id.l10n_be_codaclean_iap_token = False

        return result.get('files', [])

    def l10n_be_codaclean_action_open_settings_open_draft_soda_entries(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("journal_id", "=", self.id), ("state", "=", "draft")],
            "target": "current",
        }

    def _l10n_be_codaclean_fetch_soda_transactions(self):
        self.ensure_one()
        last_soda_date = self.env["account.move"].search([
            ("journal_id", "=", self.id),
        ], order="date DESC", limit=1).date
        if not last_soda_date:
            last_soda_date = fields.Date.today() - relativedelta(years=2)  # API goes back 2 years max
        sodas = self._l10n_be_codaclean_fetch_sodas_from_iap(fields.Date.to_string(last_soda_date))
        moves = self.env["account.move"]
        for soda in sodas:
            try:
                soda_raw_b64, soda_pdf_b64 = soda
                assert isinstance(soda_raw_b64, str)
                assert isinstance(soda_pdf_b64, str)
                attachment_soda = self.env["ir.attachment"].create({
                    "name": self.env._("Original CodaClean CODB.xml"),
                    'type': 'binary',
                    'raw': soda_raw_b64,
                })
                move = self.with_context(raise_no_imported_file=False)._l10n_be_parse_soda_file(attachment_soda, skip_wizard=True)
                if move:
                    attachment_pdf = self.env["ir.attachment"].create({
                        'name': _("Original CodaClean Payroll Statement.pdf"),
                        'type': 'binary',
                        'mimetype': 'application/pdf',
                        'raw': soda_pdf_b64,
                        'res_model': move._name,
                        'res_id': move.id,
                    })
                    move.attachment_ids += attachment_pdf + attachment_soda
                    moves += move
                    # We may have a lot of files to import, so we commit after each file so that a later error doesn't discard previous work
                    self.env.cr.commit()
            except (UserError, ValueError) as e:
                # We need to rollback here otherwise the next iteration will still have the error when trying to commit
                _logger.error("L10nBeCodaclean: Error while importing CodaClean file: %s", e)
                self.env.cr.rollback()
        return moves

    def l10n_be_codaclean_manually_fetch_soda_transactions(self):
        self.ensure_one()
        moves = self._l10n_be_codaclean_fetch_soda_transactions()
        if not moves:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": self.env._("No CODB imported"),
                    "message": self.env._("No new CODB is available for import."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", moves.ids)],
        }

    @api.model
    def _l10n_be_codaclean_fetch_coda_transactions(self, company):
        if not company.l10n_be_codaclean_is_connected:
            raise RedirectWarning(
                message=_("Not connected to Codaclean. Please check your configuration."),
                action=self.env.ref('account.action_account_config').id,
                button_text=_("Go to settings"),
            )

        codaclean_journals = self.search([
            ("bank_statements_source", "=", "l10n_be_codaclean"),
            ("bank_account_number", "!=", False),
            ("company_id", "=", company.id),
        ])
        if not codaclean_journals:
            return []

        # We fetch only coda files with a statment date after
        # - The most recent bank statement
        # - The most recent bank statement line (if there are no bank statements)
        # - The date 1 year ago (if we did not find bank statement lines either)
        last_statement_date = dict(self.env["account.bank.statement"]._read_group(
            domain=[('journal_id', 'in', codaclean_journals.ids)],
            groupby=['journal_id'],
            aggregates=['date:max'],
        ))
        # Note that there can be entries with value `False` in last_statement_date
        remaining_journals = self.browse([journal.id for journal in codaclean_journals if not last_statement_date.get(journal)])
        last_statement_line_date = dict(self.env["account.bank.statement.line"]._read_group(
            domain=[('journal_id', 'in', remaining_journals.ids)],
            groupby=['journal_id'],
            aggregates=['date:max'],
        )) if remaining_journals else {}
        date_one_year_ago = fields.Date.today() - relativedelta(years=1)

        ibans = {}  # {iban: last_date} where last_date is the date of the last bank statement or transaction
        for journal in codaclean_journals:
            iban = journal.bank_account_number.replace(" ", "").upper()
            # Note that there can be entries with value `False` in last_statement_date / last_statement_line_date
            last_date = last_statement_date.get(journal) or last_statement_line_date.get(journal) or date_one_year_ago
            ibans[iban] = min(ibans.get(iban) or last_date, last_date)
        date_from = min(ibans.values()) or date_one_year_ago

        # Format the dates
        ibans = {iban: fields.Date.to_string(date) for iban, date in ibans.items()}
        date_from = fields.Date.to_string(date_from)

        result = company._l10n_be_codaclean_fetch_coda_files(date_from, ibans)
        if not company.l10n_be_codaclean_iap_token:
            # Modify the status in a new cursor to prevent the changes from being rolled back
            with company.pool.cursor() as new_cr:
                company = company.with_env(company.env(cr=new_cr))
                company.l10n_be_codaclean_iap_token = False
        if error := result.get("error", {}):
            raise UserError(get_error_message(error))

        return result.get('files', [])

    @api.model
    def _l10n_be_codaclean_import_coda_files(self, company, codas):
        if not codas:
            return []

        statement_ids_all = []
        skipped_bank_accounts = set()
        acc_journal_map = {
            # A same account number could be formatted differently in journal.bank_account_number and
            # coda statement. Therefor we must match sanitized versions of both.
            sanitize_account_number(acc_num):
            journals for acc_num, journals in self._read_group(
                [
                    ("company_id", "=", company.id),
                    ("bank_statements_source", "in", {"l10n_be_codaclean", "undefined"}),
                ],
                ['bank_account_number'],
                ['id:recordset'],
            )
        }

        journal_stats = defaultdict(lambda: {
            "count": 0,
            "dates": [],
            "currency": None,
        })
        imported_files = 0

        for coda_b64, pdf_b64 in codas:
            try:
                assert isinstance(coda_b64, str)
                assert isinstance(pdf_b64, str)
                coda_attachment = self.env["ir.attachment"].create({
                    "name": 'codaclean_coda.coda',
                    'type': 'binary',
                    'raw': coda_b64,
                })
                statement_ids = []
                for currency, account_number, extension_number, stmt_vals in self._parse_bank_statement_file(coda_attachment.raw):
                    journals = [
                        journal for
                        journal in acc_journal_map.get(sanitize_account_number(account_number), [])
                        if (
                            (journal.currency_id and journal.currency_id.name == currency)
                            or not journal.currency_id
                        )
                    ]
                    if len(journals) > 1 and extension_number:
                        journal = next((j for j in journals if j.extension_number == extension_number), False)
                    else:
                        journal = (
                            next((j for j in journals if j.currency_id.name == currency), False)
                            or (journals[0] if journals else None)
                        )

                    if journal:
                        journal.bank_statements_source = "l10n_be_codaclean"
                    else:
                        skipped_bank_accounts.add(f"{account_number} ({currency})")
                        continue
                    stmt_vals = journal._complete_bank_statement_vals(stmt_vals, journal, account_number, coda_attachment)
                    statement_ids.extend(journal.with_context(skip_pdf_attachment_generation=True)._create_bank_statements(stmt_vals, raise_no_imported_file=False)[0])
                if statement_ids:
                    # Logging part
                    imported_files += 1
                    stats = journal_stats[journal]
                    stats['count'] += 1
                    stats['currency'] = currency
                    stats['dates'].append(stmt_vals[0].get('date'))

                    statement_ids_all.extend(statement_ids)
                    # We can not add an attachment to multiple bank statements at once.
                    # (See function `write` of model 'account.bank.statement' in module 'account'.)
                    pdf_attachment = self.env['ir.attachment'].create({
                        'name': 'codaclean_pdf.pdf',
                        'type': 'binary',
                        'mimetype': 'application/pdf',
                        'raw': pdf_b64,
                    })
                    for statement in self.env['account.bank.statement'].browse(statement_ids):
                        statement.attachment_ids |= pdf_attachment
                    # We may have a lot of statements to import, so we commit after each so that a later error doesn't discard previous work
                    if not modules.module.current_test:
                        self.env.cr.commit()
            except (UserError, ValueError) as e:
                _logger.error("Error while importing Codaclean file: %s", e)
                # We need to rollback here otherwise the next iteration will still have the error when trying to commit
                self.env.cr.rollback()

        _logger.info("L10nBeCodaClean: Coda import summary - Fetched: %s - Imported: %s - Journals: %s", len(codas), imported_files, len(journal_stats))
        for journal, stats in journal_stats.items():
            _logger.info("%s (%s): %s transactions (From: %s - To: %s) with currency %s", journal.code, journal.id, stats['count'], min(stats['dates']), max(stats['dates']), stats["currency"])

        if skipped_bank_accounts:
            _logger.info("No journals were found for the following bank accounts parsed from the Coda files: %s", ','.join(skipped_bank_accounts))
        return statement_ids_all

    def l10n_be_codaclean_manually_fetch_coda_transactions(self):
        self.ensure_one()
        codas = self._l10n_be_codaclean_fetch_coda_transactions(self.company_id)
        statement_ids = self._l10n_be_codaclean_import_coda_files(self.company_id, codas)
        return self.env["account.bank.statement.line"]._action_open_bank_reconciliation_widget(
            extra_domain=[("statement_id", "in", statement_ids)],
        )

    @api.model
    def _l10n_be_codaclean_cron_fetch_coda_transactions(self):
        coda_companies = self.env['res.company'].search([
            ('l10n_be_codaclean_is_connected', '=', True),
        ])
        if not coda_companies:
            _logger.info("No company is connected to Codaclean.")
            return
        for company in coda_companies:
            # We want to avoid raising in the cron
            try:
                codas = self._l10n_be_codaclean_fetch_coda_transactions(company)
            except (UserError, RedirectWarning) as e:
                _logger.warning("Fetching coda files for company '%s' (id = %s) failed: %s", company.name, company.id, exception_to_unicode(e))
                continue
            _logger.info("%s coda files were fetched for company '%s' (id = %s).", len(codas), company.name, company.id)
            statement_count = len(self._l10n_be_codaclean_import_coda_files(company, codas))
            _logger.info("%s bank statements were imported for company '%s' (id = %s).", statement_count, company.name, company.id)

    def _l10n_be_codaclean_cron_fetch_soda_transactions(self):
        codaclean_companies = self.env['res.company'].search([
            ('l10n_be_codaclean_is_connected', '=', True),
            ('l10n_be_codaclean_soda_journal', '!=', False),
        ])
        if not codaclean_companies:
            _logger.info("L10BeCodaclean: No company is connected to CodaClean.")
            return
        for company in codaclean_companies:
            imported_moves = company.l10n_be_codaclean_soda_journal._l10n_be_codaclean_fetch_soda_transactions()
            _logger.info("L10BeCodaclean: %s payroll statements were imported.", len(imported_moves))
