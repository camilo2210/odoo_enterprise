from odoo import models


class L10n_IEEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_ie.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Irish EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        ie_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': ie_tax_tags['goods'],
                    'name': self.env._('Goods'),
                    'shortcut': '',
                },
                'services': {
                    'tax_tag_ids': ie_tax_tags['services'],
                    'name': self.env._('Services'),
                    'shortcut': 'S',
                },
                'triangular': {
                    'tax_tag_ids': ie_tax_tags['triangular'],
                    'name': self.env._('Triangular'),
                    'shortcut': 'T',
                },
            }
        })

        super()._custom_options_initializer(report, options, previous_options)

    def _get_ec_sales_tax_tags(self):
        # Overrides account_reports
        goods_expression = self.env.ref('l10n_ie.l10n_ie_tr_E1_goods_tag')
        services_expression = self.env.ref('l10n_ie.l10n_ie_tr_ES1_tag')
        triangular_expression = self.env.ref('l10n_ie.l10n_ie_tr_E1_triangular_tag')

        return {
            'goods': goods_expression._get_matching_tags().ids,
            'services': services_expression._get_matching_tags().ids,
            'triangular': triangular_expression._get_matching_tags().ids,
        }
