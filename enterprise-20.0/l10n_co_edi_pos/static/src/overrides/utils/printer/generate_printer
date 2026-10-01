import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

patch(GeneratePrinterData.prototype, {
    // @Extend
    /**
     * Duplicate of `l10n_co_edi_pos`.`pos.order.receipt`.`order_receipt_generate_data()`
     * @returns {*}
     */
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        const co_receipt_data = this.order.l10n_co_edi_pos_receipt_data;

        if (co_receipt_data) {
            data.l10n_co_edi_pos = co_receipt_data;
        }

        return data;
    },
});
