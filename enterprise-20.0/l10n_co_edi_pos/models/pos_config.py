from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    def _default_l10n_co_edi_credit_note_journal(self):
        return self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', '=', 'sale'),
        ], limit=1)

    def _default_l10n_co_edi_final_consumer_invoices_journal(self):
        return self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(self.env.company),
            ('type', '=', 'sale'),
        ], limit=1)

    l10n_co_edi_pos_serial_number = fields.Char(string="POS Serial Number")
    l10n_co_edi_credit_note_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Credit Notes",
        check_company=True,
        domain=[('type', '=', 'sale')],
        default=_default_l10n_co_edi_credit_note_journal,
    )
    l10n_co_edi_final_consumer_invoices_journal_id = fields.Many2one(
        comodel_name='account.journal',
        string="Final Consumer Invoices",
        check_company=True,
        domain=[('type', '=', 'sale')],
        default=_default_l10n_co_edi_final_consumer_invoices_journal,
    )

    def get_limited_partners_loading(self, offset=0):
        partner_ids = super().get_limited_partners_loading(offset)
        final_consumer = self.env.ref('l10n_co_edi.consumidor_final_customer', raise_if_not_found=False)

        if final_consumer and (final_consumer.id,) not in partner_ids:
            partner_ids.append((final_consumer.id,))

        return partner_ids

    def _load_pos_data_read(self, records, config):
        # Extend point_of_sale
        data = super()._load_pos_data_read(records, config)
        if data and self.env.company.country_id.code == 'CO':
            final_consumer = self.env.ref('l10n_co_edi.consumidor_final_customer', raise_if_not_found=False)
            data[0]['_l10n_co_final_consumer_id'] = final_consumer.id if final_consumer else None

        return data
