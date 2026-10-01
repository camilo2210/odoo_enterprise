import { PosConfig } from "@point_of_sale/app/models/pos_config";
import { patch } from "@web/core/utils/patch";

patch(PosConfig.prototype, {
    get displayBigTrackingNumber() {
        return true;
    },
    get useFiscalPrinter() {
        return (
            this.company_id.country_id.code === "IT" &&
            this.receipt_printer_ids.some((p) => p.printer_type === "it_fiscal_printer")
        );
    },
    get autoPrint() {
        return this.useFiscalPrinter || super.autoPrint;
    },
});
