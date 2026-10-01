# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_bg_document_type_selection_values(self):
        # OVERRIDE l10n_bg_ledger/models/account_move
        return sorted(super()._l10n_bg_document_type_selection_values() + [
            ('04', '04 - Register of goods under the regime of storage of goods on demand, sent or transported from the territory of the country to the territory of another member state'),
            ('05', '05 - Register of goods under the regime of storage of goods on demand, received on the territory of the country'),
            ('23', '23 - Credit notification under Art. 126b, para. 1 of VAT'),
            ('29', '29 - Protocol under Art. 126b, para. 2 and 7 of VAT'),
            ('92', '92 - Protocol on the tax credit under Art. 151g, para. 8 of the law or a report under Art. 104g, para. 14'),
            ('95', '95 - Protocol for free provision of foodstuffs, to which Art. 6, para. 4, item 4 VAT'),
        ], key=lambda line: line[0])
