# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # pos.config fields
    pos_is_company_country_germany = fields.Boolean(related='pos_config_id.is_company_country_germany', readonly=False)
    pos_l10n_de_create_tss_flag = fields.Boolean(related='pos_config_id.l10n_de_create_tss_flag', readonly=False)
    pos_l10n_de_fiskaly_client_id = fields.Char(related='pos_config_id.l10n_de_fiskaly_client_id', string="Fiskaly Client ID")
    pos_l10n_de_fiskaly_tss_id = fields.Char(related='pos_config_id.l10n_de_fiskaly_tss_id')

    def action_create_tss(self):
        """Sets the flag to trigger Fiskaly client and TSS creation, which is a one-way process and cannot be reverted."""
        self.pos_l10n_de_create_tss_flag = True
