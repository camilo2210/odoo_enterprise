import { patch } from "@web/core/utils/patch";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";
import { resolveDeviceAddress } from "@obox_pos_mobile/app/utils/device_address";

patch(PosTicketPrinterPlugin.prototype, {
    async createPrinterInstance(printer) {
        if (printer.printer_type === "obox") {
            printer.printer_ip = await resolveDeviceAddress(printer.printer_ip);
        }
        return await super.createPrinterInstance(...arguments);
    },
});
