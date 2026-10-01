# Part of Odoo. See LICENSE file for full copyright and licensing details.
import csv
import io

from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Date
from odoo.tools import float_repr, float_round
from odoo.addons.account_reports.utils.report_data_objects import AccountReportColumnData


class L10nPhBoaReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.report.handler"
    _inherit = ["account.report.custom.handler"]
    _description = "Base Custom Handler that adds support for direct CSV export."

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options=previous_options)
        options["force_landscape_printing"] = True
        options["custom_display_config"]["pdf_export"] = {
            "company_information": "l10n_ph_reports.company_information",
            "internal_layout": "l10n_ph_reports.internal_layout",
        }
        options.setdefault("buttons", []).append({
            "name": self.env._("CSV"),
            "action": "export_file",
            "action_param": "print_report_to_csv",
            "file_export_type": self.env._("CSV"),
            "sequence": -10,
            "branch_allowed": False,
            "always_show": True
        })
        for button in options["buttons"]:
            if button.get("action_param") == "export_to_xlsx":
                button["always_show"] = False

        # Automatically unfold the report when printing it, unless selected report variant has manually unfolded lines
        has_unfolded_lines = any(report._parse_line_id(line)[0][-1] == options["selected_variant_id"]
            for line in options.get("unfolded_lines") or [])
        options["unfold_all"] = (options["export_mode"] == "print" and not has_unfolded_lines) or options["unfold_all"]

    def _get_csv_row_from_line(self, line, options):
        """Hook for child reports.
        Process a single report line and return a list of strings for the row.
        Return None to skip the line (e.g., for totals or group headers).
        """
        raise NotImplementedError

    def _generate_csv_file(self, options):
        """Generates a CSV (no headers per regulation)."""
        report = self.env["account.report"].browse(options["report_id"])
        options = report.get_options(previous_options={**options, "export_mode": "print", "unfold_all": True})
        output = io.StringIO()
        data_rows_written = 0
        for line in report._get_lines(options):
            row_data = self._get_csv_row_from_line(line, options)

            if row_data:
                csv.writer(output, quoting=csv.QUOTE_ALL).writerow(row_data)
                data_rows_written += 1

        if data_rows_written == 0:
            if options.get("_running_export_test"):
                return output.getvalue().encode("utf-8")
            raise UserError(
                self.env._(
                    "There are no visible records to export. Try unfolding lines or expand the scope of the report."
                ),
            )

        return output.getvalue().encode("utf-8")

    def print_report_to_csv(self, options):
        """Act as a smart dispatcher for CSV file exports.
        Identifies the currently active report from the options and delegates
        the file generation to its specific custom handler.
        """
        report = self.env["account.report"].browse(options["report_id"])
        report_handler = self.env[report.custom_handler_model_name]
        report_name = report.name.replace(" ", "")
        raw_date = options.get("date", {}).get("date_from")
        report_date = Date.to_date(raw_date) if raw_date else Date.context_today(self)
        return {
            "file_name": f"BOA_{report_name}_{report_date.strftime('%m%Y')}.csv",
            "file_content": report_handler._generate_csv_file(options),
            "file_type": "csv",
        }

    # ------------------
    #  Helpers
    # ------------------

    def _boa_clean(self, value):
        """Flattens multiline strings and (if applicable) grabs name from dict."""
        if isinstance(value, AccountReportColumnData):
            value = value.name or ''
        return str(value).replace("\n", " ").strip()

    def _boa_format(self, value):
        """Returns a string representation of a float with company-set decimal places."""
        dp = self.env.company.currency_id.decimal_places
        return float_repr(float_round(value, dp), dp)

    def _boa_map_cols(self, line, options):
        """Maps expression_label to column data."""
        if not line.columns:
            return {}

        return {
            opt_col.get("expression_label"): line_col
            for opt_col, line_col in zip(options.get("columns", []), line.columns, strict=False)
        }

    def _boa_get_str(self, cols, label):
        """Grabs and cleans a string label."""
        return self._boa_clean(cols.get(label))

    def _boa_get_amt(self, cols, label):
        """Grabs and cleans a float label, via the 'no_format' value."""
        val = cols.get(label, {}).no_format or 0.0
        return self._boa_format(val)
