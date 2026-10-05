# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    def _prepare_urbanpiper_data(self, urbanpiper_store, product_ids):
        self.ensure_one()
        tax_data = super()._prepare_urbanpiper_data(urbanpiper_store, product_ids)
        if urbanpiper_store.country_code != 'IN' or not tax_data:
            return tax_data

        sgst_group, cgst_group = map(
            self.env['account.chart.template'].with_company(self.company_id).ref,
            ('sgst_group', 'cgst_group')
        )
        if self.tax_group_id not in [sgst_group, cgst_group]:
            return False
        tax_title = 'CGST' if self.tax_group_id == cgst_group else 'SGST'
        return {
            **tax_data,
            'code': tax_title + '_P',
            'title': tax_title,
        }
