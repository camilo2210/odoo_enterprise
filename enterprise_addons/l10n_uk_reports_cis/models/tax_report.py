from odoo import models, _
from odoo.tools import SQL, float_round


class AccountTaxReportHandler(models.AbstractModel):
    _inherit = 'account.tax.report.handler'


class BritishCISTaxReportCustomHandler(models.AbstractModel):
    _name = 'cis.tax.report.handler'
    _inherit = 'account.tax.report.handler'
    _description = 'British Tax Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(report, options, previous_options)
        options['ignore_totals_below_sections'] = True

        purchase_base_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_base')._get_matching_tags()
        sales_base_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_sale_expr_base')._get_matching_tags()
        tags = purchase_base_tags + sales_base_tags

        # We need to test on base tags instead of tax tags because the gross tax does not create a line.
        options['forced_domain'] = [*options.get('forced_domain', []), ('move_id.line_ids.tax_ids.repartition_line_ids.tag_ids', 'in', tags.ids)]

    def _report_engine_cis_materials_purchase(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        purchase_base_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_purchase_expr_base')._get_matching_tags()
        domain = f"[('display_type', '=', 'product'), ('move_id.move_type', 'in', ('in_invoice', 'in_refund', 'in_receipt')), ('tax_tag_ids', 'not in', {purchase_base_tags.ids})]"
        expressions = next(iter(formulas_dict.values()))
        result = report._report_engine_domain(options, 'strict_range', {domain: expressions}, current_groupby, warnings)
        return {next(iter(formulas_dict.values())):  result[expressions]}

    def _report_engine_cis_materials_sales(self, options, date_scope, formulas_dict, current_groupby, warnings=None):
        report = self.env['account.report'].browse(options['report_id'])
        sales_base_tags = self.env.ref('l10n_uk_reports_cis.account_uk_cis_report_line_sale_expr_base')._get_matching_tags()
        domain = f"[('display_type', '=', 'product'), ('move_id.move_type', 'in', ('out_invoice', 'out_refund', 'out_receipt')), ('tax_tag_ids', 'not in', {sales_base_tags.ids})]"
        expressions = next(iter(formulas_dict.values()))
        result = report._report_engine_domain(options, 'strict_range', {domain: expressions}, current_groupby, warnings)
        return {next(iter(formulas_dict.values())):  result[expressions]}

    def _custom_line_postprocessor(self, report, options, lines):
        for column_index, column in enumerate(options['columns']):
            if column['expression_label'] in ('payment', 'materials'):
                for line in lines:
                    column_data = line.columns[column_index]
                    value = float_round(column_data.no_format, precision_digits=0, rounding_method='DOWN')
                    line.columns[column_index] = report._build_column_data(value, column)

        return lines

    def _customize_warnings(self, report, options, all_column_groups_expression_totals, warnings):
        queries = []
        for column_group_index in all_column_groups_expression_totals:
            column_group_options = report._get_column_group_options(options, column_group_index)
            queries.append(
                SQL(
                    """
                    SELECT
                    COALESCE(
                        ARRAY_AGG(DISTINCT move.partner_id),
                        '{}'
                    ) AS unregistered_partners
                    FROM account_move move
                    WHERE move.l10n_uk_cis_inactive_partner = TRUE
                    AND move.date >= %(period_start)s
                    AND move.date <= %(period_end)s
                    """,
                    period_start=column_group_options['date']['date_from'],
                    period_end=column_group_options['date']['date_to'],
                )
            )

        self.env.cr.execute(SQL(" UNION ALL ").join(queries))
        result = self.env.cr.dictfetchall()
        unregistered_partners = list({
            id for column_group_result in result
            for id in column_group_result['unregistered_partners']
        })

        if unregistered_partners:
            warnings['l10n_uk_reports_cis.warning_cis_unregistered_partner'] = {
                'partner_ids': unregistered_partners,
                'alert_type': 'warning'
            }

    def action_open_partners_view_with_unregistered_cis(self, options, params=None):
        partner_ids = params.get('partner_ids')
        partners = self.env['res.partner'].browse(partner_ids)
        name = _("Unregistered partners") if len(partners) > 1 else _("Unregistered partner")
        return partners._get_records_action(name=name)
