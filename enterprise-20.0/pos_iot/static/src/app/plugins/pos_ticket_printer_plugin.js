import { patch } from "@web/core/utils/patch";
import { IoTPrinter } from "../utils/printer/iot_printer";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    async createPrinterInstance(printer) {
        if (printer.printer_type === "iot") {
            if (!printer.iot_device_id?.identifier || !printer.iot_device_id?.iot_id) {
                console.error("Error loading data, missing Iot Box or device");
                return false;
            }
            return new IoTPrinter({
                printer,
                iotHttp: this.env.services.iot_http,
            });
        }

        return await super.createPrinterInstance(...arguments);
    },
});
