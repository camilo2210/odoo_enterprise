# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10nPhBoaGeneralLedgerReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.general.ledger.report.handler"
    _inherit = ["l10n_ph.boa.report.handler", "account.general.ledger.report.handler"]
    _description = "Book of Accounts - General Ledger Custom Handler"

    # ================
    # .CSV file export
    # ================

    def _get_csv_row_from_line(self, line, options):
        report = self.env["account.report"].browse(options["report_id"])
        _markup, model, _res_id = report._parse_line_id(line.id)[-1]
        if model == "account.account":
            options["current_account"] = line.name or ''
            return None

        if line.caret_options != "id_with_accumulated_balance_caret":
            return None

        cols = self._boa_map_cols(line, options)
        account_code, account_name = options.get("current_account", "Unknown Account").split(" ", 1)
        return [
            self._boa_clean(account_code),
            self._boa_clean(account_name),
            self._boa_clean(line.name),
            self._boa_get_str(cols, "date"),
            self._boa_get_amt(cols, "debit"),
            self._boa_get_amt(cols, "credit"),
            self._boa_get_amt(cols, "balance"),
        ]
