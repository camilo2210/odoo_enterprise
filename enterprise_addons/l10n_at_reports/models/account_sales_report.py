# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# Copyright (c) 2022 WT-IO-IT GmbH (https://www.wt-io-it.at)
#                    Mag. Wolfgang Taferner <wolfgang.taferner@wt-io-it.at>
from odoo import models


class L10n_AtEcSalesReportHandler(models.AbstractModel):
    _name = 'l10n_at.ec.sales.report.handler'
    _inherit = ['account.ec.sales.with.tags.report.handler']
    _description = 'Austrian EC Sales Report Custom Handler'

    def _custom_options_initializer(self, report, options, previous_options):
        at_tax_tags = self._get_ec_sales_tax_tags()
        options.update({
            'sales_report_operation_types': {
                'goods': {
                    'tax_tag_ids': at_tax_tags['goods'],
                    'name': self.env._('Goods'),
                    'shortcut': 'L',
                },
                'services': {
                    'tax_tag_ids': at_tax_tags['services'],
                    'name': self.env._('Services'),
                    'shortcut': 'S',
                },
                'triangular': {
                    'tax_tag_ids': at_tax_tags['triangular'],
                    'name': self.env._('Triangular'),
                    'shortcut': 'D'
                },
            }
        })
        super()._custom_options_initializer(report, options, previous_options)

    def _get_ec_sales_tax_tags(self):
        goods = (
            self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_igl_tag') +
            self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_4_8_tag') +
            self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_4_9_tag')
        )
        triangular = self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_igl3_tag')
        services = self.env.ref('l10n_at.tax_report_line_l10n_at_tva_line_3_zm_dl_tag')

        return {
            'goods': tuple(goods._get_matching_tags().ids),
            'triangular': tuple(triangular._get_matching_tags().ids),
            'services': tuple(services._get_matching_tags().ids),
        }
