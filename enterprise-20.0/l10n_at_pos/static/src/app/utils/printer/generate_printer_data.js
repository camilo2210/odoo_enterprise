import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.conditions.l10n_at_cash_regid = Boolean(this.order.config.l10n_at_cash_regid);
        data.extra_data.l10n_at_cash_regid = this.order.config.l10n_at_cash_regid || "";
        if (this.order.l10n_at_pos_order_receipt_qr_data) {
            data.image.l10n_at_pos_order_receipt_qr_data =
                "data:image/png;base64," + this.order.l10n_at_pos_order_receipt_qr_data;
        }

        return data;
    },
});
