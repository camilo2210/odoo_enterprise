# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    def _prepare_urbanpiper_data(self, urbanpiper_store, product_ids):
        """
        # Part of Menu Sync
        Prepare UrbanPiper-compatible tax payload for menu synchronization.

        Returns a formatted tax dictionary for sale taxes, or False if the tax
        is not applicable for syncing.
        """
        self.ensure_one()
        tax_config_by_country = {
            'US': ('ST_P', 'Sales Tax'),
            'CA': ('GST_P', 'GST'),
        }
        code, title = tax_config_by_country.get(urbanpiper_store.country_code, ('VAT_P', 'VAT'))
        return {
            'code': code,
            'title': title,
            'active': True,
            'item_ref_ids': [str(product_id) for product_id in product_ids],
            'structure': {
                'value': self.amount,
            },
        }
