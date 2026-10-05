from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_tr_nilvera_customer_alias_id = fields.Many2one(
        comodel_name='l10n_tr.nilvera.alias',
        string="eInvoice Alias",
        compute='_compute_nilvera_customer_alias_id',
        domain="[('partner_id', '=', id)]",
        copy=False,
        store=True,
        readonly=False,
        help="Specifies the alias provided by Nilvera, used when sending electronic invoices. \n"
        "It helps make sure your customer is correctly recognized by the GİB when e-invoices are sent. \n"
        "This ID is needed for your invoices to be processed correctly and comply with Turkish tax rules.",
    )

    @api.depends('l10n_tr_nilvera_customer_alias_ids', 'l10n_tr_nilvera_customer_status')
    def _compute_nilvera_customer_alias_id(self):
        for record in self:
            if record.l10n_tr_nilvera_customer_status == 'einvoice' and not record.l10n_tr_nilvera_customer_alias_id:
                record.l10n_tr_nilvera_customer_alias_id = record.l10n_tr_nilvera_customer_alias_ids[:1]
            elif record.l10n_tr_nilvera_customer_status == 'earchive':
                record.l10n_tr_nilvera_customer_alias_id = False

    def _get_edi_builder(self, invoice_edi_format):
        # EXTENDS 'account_edi_ubl_cii'
        if invoice_edi_format == 'ubl_tr':
            return self.env['account.edi.xml.ubl.tr']
        return super()._get_edi_builder(invoice_edi_format)

    def _get_ubl_cii_formats_info(self):
        # EXTENDS 'account_edi_ubl_cii'
        formats_info = super()._get_ubl_cii_formats_info()
        formats_info['ubl_tr'] = {'countries': ['TR']}
        return formats_info
