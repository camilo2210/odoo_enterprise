import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        const isBlackboxed = !!this.order.config.iot_fdm_se_id;
        data.conditions.iot_fdm_se_id = isBlackboxed;

        if (isBlackboxed) {
            data.extra_data.l10n_se_pos_type = this.order.seType;
            data.extra_data.l10n_se_pos_original_date =
                this.order.create_date.toFormat("HH:mm dd/MM/yyyy");
        }

        return data;
    },
});
