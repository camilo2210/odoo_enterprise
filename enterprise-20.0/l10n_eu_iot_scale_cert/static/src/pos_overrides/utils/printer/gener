import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        data.conditions.l10n_eu_iot_scale_cert_show_warning = this.order.showCertificationWarning;
        return data;
    },

    generateLineData() {
        const lines = super.generateLineData();
        return lines
            .map((line, index) => ({
                ...line,
                show_uom: this.order.lines[index].product_id.uom_id.id !== this.config._unit_uom_id,
                qty_full_precision: this.order.lines[index].getQuantityStr().qtyStr,
            }))
            .filter((line, index) => !this.order.lines[index].uiState.isDeleted);
    },
});
