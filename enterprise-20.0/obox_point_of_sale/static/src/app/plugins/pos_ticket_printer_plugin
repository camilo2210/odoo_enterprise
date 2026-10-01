import { patch } from "@web/core/utils/patch";
import { EpsonPrinter } from "@point_of_sale/app/utils/printer/epson_printer";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    async createPrinterInstance(printer) {
        if (printer.printer_type === "obox") {
            return new EpsonPrinter({ printer });
        }

        return await super.createPrinterInstance(...arguments);
    },
    get hasProxyPreparationPrinters() {
        return this.preparationPrinters.some((printer) => printer.proxy_obox_id);
    },
});
