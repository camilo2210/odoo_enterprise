# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api

ITSME_LOGO = '/sign_itsme/static/img/itsme_logo.png'


class SignItemRole(models.Model):
    _inherit = "sign.item.role"

    auth_method = fields.Selection(selection_add=[
        ('itsme', 'Identification via itsme®'),
        ('itsme_qes', 'Qualified Signature via itsme®'),
    ], ondelete={'itsme': 'cascade', 'itsme_qes': 'cascade'})

    @api.model
    def _get_auth_method_iap_mapping(self):
        iap_map = super()._get_auth_method_iap_mapping()
        iap_map.update(itsme='itsme_proxy')
        return iap_map

    def _compute_requires_external_signature(self):
        super()._compute_requires_external_signature()
        self.filtered(lambda role: role.auth_method == 'itsme_qes').requires_external_signature = True

    def _get_external_signature_provider(self):
        if self.auth_method == 'itsme_qes':
            return 'itsme'
        return super()._get_external_signature_provider()

    def _get_external_signature_provider_name(self):
        if self.auth_method == 'itsme_qes':
            return 'itsme®'
        return super()._get_external_signature_provider_name()

    def _get_external_signature_provider_logo_path(self):
        if self.auth_method == 'itsme_qes':
            return ITSME_LOGO
        return super()._get_external_signature_provider_logo_path()
