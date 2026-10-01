# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models


class L10nPhBoaAccountAgedPartnerBalanceReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.account.aged.partner.balance.report.handler"
    _inherit = ["l10n_ph.boa.report.handler"]
    _description = "Book of Accounts - Aged Partner Balance Custom Handler"

    def _get_csv_row_from_line(self, line, options):
        report = self.env["account.report"].browse(options["report_id"])
        _markup, model, _res_id = report._parse_line_id(line.id)[-1]
        if model != "account.move.line":
            return None

        cols = self._boa_map_cols(line, options)
        return [
            self._boa_clean(line.name),
            self._boa_get_str(cols, "invoice_date"),
            self._boa_get_amt(cols, "period0"),
            self._boa_get_amt(cols, "period1"),
            self._boa_get_amt(cols, "period2"),
            self._boa_get_amt(cols, "period3"),
            self._boa_get_amt(cols, "period4"),
            self._boa_get_amt(cols, "period5"),
        ]


class L10nPhBoaAgedReceivableReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.aged.receivable.report.handler"
    _inherit = ["l10n_ph.boa.account.aged.partner.balance.report.handler", "account.aged.receivable.report.handler"]
    _description = "Book of Accounts - Aged Receivable Custom Handler"


class L10nPhBoaAgedPayableReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.aged.payable.report.handler"
    _inherit = ["l10n_ph.boa.account.aged.partner.balance.report.handler", "account.aged.payable.report.handler"]
    _description = "Book of Accounts - Aged Payable Custom Handler"
