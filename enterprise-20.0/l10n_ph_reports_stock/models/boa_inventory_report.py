# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.fields import Datetime, Domain
from odoo.tools.date_utils import end_of
from odoo.tools.float_utils import float_is_zero
from odoo.addons.account_reports.utils.report_data_objects import AccountReportLineData


class L10nPhBoaInventoryReportHandler(models.AbstractModel):
    _name = "l10n_ph.boa.inventory.report.handler"
    _inherit = "l10n_ph.boa.report.handler"
    _description = "PH Inventory Report Handler"

    LEVEL_ROOT, LEVEL_PRODUCT = 1, 3

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(report, options, previous_options)
        options["ignore_totals_below_sections"] = True
        options["filter_no_stock"] = previous_options.get("filter_no_stock", True)
        options.setdefault("custom_display_config", {}).setdefault("components", {})["AccountReportFilters"] = "L10nPHReportStockFilters"

    def _dynamic_lines_generator(self, report, options, all_column_groups_expression_totals=None, warnings=None):
        return [(0, AccountReportLineData(
            id=report._get_generic_line_id(None, None, markup="root"),
            name="Product Name",
            level=self.LEVEL_ROOT,
            unfoldable=False,
            unfolded=True,
            expand_function="_report_expand_unfoldable_line_l10n_ph_inventory_root",
            columns=[report._build_column_data("", col) for col in options["columns"]],
        ))]

    def _report_expand_unfoldable_line_l10n_ph_inventory_root(self, line_dict_id, groupby, options, unfold_all_batch_data=None, limit_to_load=None):
        report = self.env["account.report"].browse(options["report_id"])
        eod = end_of(Datetime.to_datetime(options["date"]["date_to"]), "day")
        domain = Domain("is_storable", "=", True)
        if options.get("filter_no_stock"):
            domain &= Domain("qty_available", ">", 0)

        products = self.env["product.product"].with_context(to_date=eod).search(domain, order="default_code, name, id")
        lines = []
        for product in products:
            if limit_to_load and len(lines) >= limit_to_load:
                break
            product_attr = product.product_template_attribute_value_ids._get_combination_name()
            lines.append(AccountReportLineData(
                id=report._get_generic_line_id("product.product", product.id, parent_line_id=line_dict_id),
                parent_id=line_dict_id,
                name=f"{product.name} ({product_attr})" if product_attr else product.name,
                level=self.LEVEL_PRODUCT,
                columns=[
                    report._build_column_data({
                        "default_code": product.default_code or "",
                        "qty_available": product.qty_available or 0.0,
                        "uom": product.uom_id.name or "Units",
                        "avg_cost": product.avg_cost or 0.0,
                        "value": product.total_value or 0.0,
                    }.get(col["expression_label"]), col)
                    for col in options["columns"]
                ],
            ))

        load_more_count = max(len(products) - limit_to_load, 0) if limit_to_load else 0
        if load_more_count:
            lines.append(report._create_load_more_line(
                self.env["account.report.line"],  # little hack since we don't have a real report line here
                line_dict_id,
                options,
                None,
                load_more_count,
                self.LEVEL_PRODUCT,
                groupby,
                "_report_expand_unfoldable_line_l10n_ph_inventory_root",
                None
            ))

        return lines

    # ================
    # .CSV file export
    # ================

    def _get_csv_row_from_line(self, line, options):
        report = self.env["account.report"].browse(options["report_id"])
        _markup, model, _res_id = report._parse_line_id(line.id)[-1]
        if model != "product.product":
            return None

        cols = self._boa_map_cols(line, options)
        qty = cols.get("qty_available", {}).no_format or 0.0
        if options.get("filter_no_stock") and float_is_zero(qty, precision_digits=1):
            return None

        return [
            options.get("date", {}).get("date_to", ""),
            self._boa_clean(line.name),
            self._boa_get_str(cols, "default_code"),
            self._boa_format(qty),
            self._boa_get_str(cols, "uom"),
            self._boa_get_amt(cols, "avg_cost"),
            self._boa_get_amt(cols, "value"),
        ]
