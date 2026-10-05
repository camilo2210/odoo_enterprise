# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class SignTemplate(models.Model):
    _inherit = 'sign.template'

    def check_emsigner_constraint(self):
        """ Whether the template breaks the Aadhaar single signer/document rule
        (emsigner works only with a single signer and a single document). """
        self.ensure_one()
        emsigner_roles = self.sign_item_ids.responsible_id.filtered(
            lambda role: role.auth_method == 'emsigner'
        )
        multiple_documents = len(self.document_ids) > 1
        return bool((multiple_documents and emsigner_roles) or len(emsigner_roles) > 1)
