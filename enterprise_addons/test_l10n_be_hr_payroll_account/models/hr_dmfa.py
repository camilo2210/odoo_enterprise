# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class L10n_BeDmfa(models.Model):
    _inherit = 'l10n_be.dmfa'

    def action_open_dmfa_sandbox_answer_wizard(self):
        self.ensure_one()
        declaration = self.onss_declaration_ids.sorted('id')[-1:]
        if not declaration:
            raise UserError(_("Post the declaration first: the ONSS only answers to posted declarations."))
        return declaration.action_open_dmfa_sandbox_answer_wizard()
