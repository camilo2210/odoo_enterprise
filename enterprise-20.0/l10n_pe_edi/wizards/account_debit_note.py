# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models
from odoo.addons.l10n_pe_edi.models.account_move import DEBIT_REASON


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    l10n_pe_edi_charge_reason = fields.Selection(
        selection=DEBIT_REASON,
        string="Debit Reason",
        default='01',
        help="It contains all possible values for the refund reason according to Catalog No. 10")

    def _prepare_default_values(self, move):
        # OVERRIDE
        values = super()._prepare_default_values(move)
        if self.country_code == 'PE' and move.l10n_latam_use_documents:
            values.update({
                'l10n_pe_edi_charge_reason': self.l10n_pe_edi_charge_reason,
                'l10n_latam_document_type_id': self.env.ref('l10n_pe.document_type08').id
            })
        return values
