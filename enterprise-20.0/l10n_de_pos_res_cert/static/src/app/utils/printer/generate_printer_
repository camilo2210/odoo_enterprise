import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";

/**
 * This class is a JS copy of the class PosOrderReceipt in Python.
 */
patch(GeneratePrinterData.prototype, {
    getTssValues() {
        const order = this.order;
        if (
            order.isCountryGermanyAndFiskaly() &&
            order.config.module_pos_restaurant &&
            order.isTransactionFinished()
        ) {
            return [
                ...super.getTssValues(),
                {
                    name: "TSE-Erstbestellung",
                    value: order.l10n_de_fiskaly_time_start
                        ?.toUTC()
                        .toFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"),
                },
            ];
        }
        return super.getTssValues();
    },
});
