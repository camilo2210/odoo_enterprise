import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);

        if (this.company.country_id.code !== "PE" || !this.order.account_move) {
            return data;
        }

        const conditions = data.conditions;
        const extraData = data.extra_data;
        const image = data.image;

        conditions.code_pe = true;
        extraData.report_name = this.order.account_move.l10n_latam_document_type_id?.report_name;
        extraData.invoice_name = this.order.invoiceName;

        const ediData = this.order.l10n_pe_edi_data;
        if (ediData) {
            conditions.has_pe_edi_data = true;
            extraData.amount_in_word = ediData.amount_to_text;
            extraData.summary = ediData.qr_str?.split("|")?.at(-2);
            image.l10n_pe_edi_pos_qrsrc = this.generateQrCode(ediData.qr_str);
        }

        return data;
    },
});
