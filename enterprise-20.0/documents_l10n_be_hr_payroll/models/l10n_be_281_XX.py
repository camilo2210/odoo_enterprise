# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class L10n_Be281_XX(models.Model):
    _inherit = 'l10n_be.281_xx'

    def _get_declaration_write_values(self):
        res = super()._get_declaration_write_values()
        res.update({
            'pdf_to_post': True,
            'document_id': False,
        })
        return res

    def action_mark_as_done(self):
        self.ensure_one()
        declarations = self._get_target_declarations()
        if declarations:
            filenames = [f for f in declarations.mapped('pdf_filename') if f]
            if filenames:
                self.env['documents.document'].search([
                    ('res_id', 'in', declarations.ids),
                    ('name', 'in', filenames),
                ]).unlink()

        return super().action_mark_as_done()
