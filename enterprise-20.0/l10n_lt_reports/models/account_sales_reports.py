from odoo import models


class LithuaniaEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_lt.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Lithuanian EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        lt_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': lt_tax_tags['goods'],
                },
                'services': {
                    'tax_tag_ids': lt_tax_tags['services'],
                },
                'triangular': {
                    'tax_tag_ids': lt_tax_tags['triangular'],
                },
            },
        })

        super()._custom_options_initializer(report, options, previous_options)

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = self.env.ref('l10n_lt.tax_report_line_18_tag')
        services_expression = self.env.ref('l10n_lt.tax_report_line_20_eu_tag')
        triangular_expression = self.env.ref('l10n_lt.tax_report_line_18_triangular_tag')

        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }
