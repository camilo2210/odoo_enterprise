# -*- coding: utf-8 -*-

from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_mx_edi_pac = fields.Selection(related='company_id.l10n_mx_edi_pac', readonly=False)
    l10n_mx_edi_pac_test_env = fields.Boolean(related='company_id.l10n_mx_edi_pac_test_env', readonly=False)
    l10n_mx_edi_pac_username = fields.Char(related='company_id.l10n_mx_edi_pac_username', readonly=False)
    l10n_mx_edi_pac_password = fields.Char(related='company_id.l10n_mx_edi_pac_password', readonly=False)
    l10n_mx_edi_certificate_ids = fields.One2many(related='company_id.l10n_mx_edi_certificate_ids', readonly=False)
    l10n_mx_edi_fiscal_regime = fields.Selection(related='company_id.l10n_mx_edi_fiscal_regime', readonly=False)
    l10n_mx_edi_global_invoice_sequence_prefix = fields.Char(related='company_id.l10n_mx_edi_global_invoice_sequence_prefix', readonly=False)
    l10n_mx_edi_factoring_account_id = fields.Many2one(related='company_id.l10n_mx_edi_factoring_account_id', readonly=False)
    l10n_mx_edi_last_sync = fields.Date(related='company_id.l10n_mx_edi_last_sync')

    def action_open_efirma_certificates(self):
        self.ensure_one()

        return {
            'name': _('E-Firma Certificates'),
            'type': 'ir.actions.act_window',
            'res_model': 'certificate.certificate',
            'view_mode': 'list,form',
            'context': {
                'default_scope': 'e_firma'
            },
            'domain': [('scope', '=', 'e_firma')],
        }
