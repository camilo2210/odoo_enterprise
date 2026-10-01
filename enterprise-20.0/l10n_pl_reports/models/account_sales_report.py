from odoo import models


class L10nPlReportsEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_pl_reports.ec.sales.report.handler'
    _inherit = ['account.ec.sales.report.handler.common']
    _description = "Polish EC Sales Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        """
        Add the invoice lines search domain that is specific to the country.
        Typically, the taxes account.report.expression ids relative to the country for the triangular, sale of goods
        or services.
        :param dict options: Report options
        :return dict: The modified options dictionary
        """
        super()._init_core_custom_options(report, options, previous_options)
        ec_operation_category = options.setdefault('sales_report_taxes', {})
        ec_operation_category.update(self._get_ec_sales_tax_tags())
        # Change the names of the taxes to specific ones that are dependant to the tax type
        ec_operation_category['operation_category'] = {
            'goods': '1',
            'triangular': '2',
            'services': '3',
        }

        options.update({'sales_report_taxes': ec_operation_category})

    def _get_ec_sales_tax_tags(self):
        goods = self.env.ref('l10n_pl.account_tax_report_line_dostawa_towarow_tag')
        services = self.env.ref('l10n_pl.account_tax_report_line_poza_kraj_tag') | self.env.ref('l10n_pl.account_tax_report_line_uslugi_art_100_1_4_tag')
        return {
            'goods': tuple(goods._get_matching_tags().ids),
            'triangular': tuple(),
            'services': tuple(services._get_matching_tags().ids),
        }
