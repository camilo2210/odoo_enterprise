# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        res = super()._load_menus_blacklist()
        if self.env.user.has_group('documents.group_documents_manager'):
            res.append(self.env.ref('documents_spreadsheet.menu_technical_my_spreadsheet_template').id)
        return res
