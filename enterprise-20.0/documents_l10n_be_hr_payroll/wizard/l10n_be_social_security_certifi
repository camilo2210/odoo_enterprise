# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class L10nBeSocialSecurityCertificate(models.TransientModel):
    _inherit = 'l10n.be.social.security.certificate'

    def _post_process_generated_file(self, data, filename):
        self.company_id._create_payroll_managers_document(data, filename)
        return super()._post_process_generated_file(data, filename)
