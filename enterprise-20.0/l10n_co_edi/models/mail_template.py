from odoo import models, api
from odoo.tools.translate import TranslationImporter


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    @api.model
    def _create_dian_mail_templates(self):
        """ This function is needed to create the DIAN mail templates because `copy_data` is overridden
        in mail, ignoring the default name passed when calling `copy`.

        This method should be idempotent, because it is called each time the module is updated.
        """
        dian_subject = (
            "{{ object.company_id.partner_id._get_vat_without_verification_code() }};"
            "{{ object.company_id.name }};{{ object.name }};{{ (object.l10n_co_edi_type or '') }};"
            "{{ object.company_id.partner_id.l10n_co_edi_commercial_name }}"
        )

        invoice_template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        invoice_template_co_xmlid = 'l10n_co_edi.email_template_edi_invoice'
        if invoice_template and not self.env.ref(invoice_template_co_xmlid, raise_if_not_found=False):
            invoice_dian_template = invoice_template.copy({"subject": dian_subject})
            invoice_dian_template.name = "Invoice (DIAN): Sending"
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': invoice_template_co_xmlid,
                'record': invoice_dian_template,
                'noupdate': True,
            }])

        credit_note_template = self.env.ref('account.email_template_edi_credit_note', raise_if_not_found=False)
        credit_note_template_co_xmlid = 'l10n_co_edi.email_template_edi_credit_note'
        if credit_note_template and not self.env.ref(credit_note_template_co_xmlid, raise_if_not_found=False):
            credit_note_dian_template = credit_note_template.copy({"subject": dian_subject})
            credit_note_dian_template.name = "Credit Note (DIAN): Sending"
            self.env['ir.model.data']._update_xmlids([{
                'xml_id': credit_note_template_co_xmlid,
                'record': credit_note_dian_template,
                'noupdate': True,
            }])

    @api.model
    def _sync_dian_mail_templates_translations(self, langs):
        pairs = [
            ('account.email_template_edi_invoice', 'l10n_co_dian.email_template_edi_invoice'),
            ('account.email_template_edi_credit_note', 'l10n_co_dian.email_template_edi_credit_note'),
        ]

        translation_importer = TranslationImporter(self.env.cr, verbose=False)

        for src_xmlid, dian_xmlid in pairs:
            src = self.env.ref(src_xmlid, raise_if_not_found=False)

            fields_to_sync = ['body_html', 'description', 'name']

            for field in fields_to_sync:
                existing_translations, _ = src.get_field_translations(field, langs)

                for lang in langs:
                    translation_value = next(t['value'] for t in existing_translations if t['lang'] == lang)
                    translation_importer.model_translations['mail.template'][field][dian_xmlid][lang] = translation_value
                    translation_importer.imported_langs.add(lang)

        translation_importer.save()
