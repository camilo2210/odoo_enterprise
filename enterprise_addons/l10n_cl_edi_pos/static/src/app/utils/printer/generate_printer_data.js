import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.conditions.code_cl = this.order.company.country_id.code === "CL";

        if (this.order.company.country_id.code === "CL") {
            const move = this.order.account_move;
            const image = move?.l10n_cl_sii_barcode_image;
            data.image.l10n_cl_sii_barcode_image = image;
            data.extra_data.l10n_cl_edi_pos_tip = this.formatCurrency(this.order.priceExcl * 0.1);
            data.extra_data.l10n_latam_document_type_name = move?.l10n_latam_document_type_id?.name;
            data.extra_data.l10n_latam_document_number = move?.l10n_latam_document_number;
            data.extra_data.l10n_cl_sii_regional_office_name =
                this.order.config._l10n_cl_sii_regional_office_selection[
                    this.order.company_id.l10n_cl_sii_regional_office
                ];
            data.extra_data.formatted_l10n_cl_dte_resolution_date =
                this.order.company.formatDateOrTime("l10n_cl_dte_resolution_date", "date");
        }

        return data;
    },
});
