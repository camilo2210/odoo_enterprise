import { patch } from "@web/core/utils/patch";
import mobile from "@web_mobile/js/services/core";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    _print(window) {
        if (mobile.polyfills.printHTML) {
            mobile.polyfills.printHTML(window.document.documentElement.outerHTML);
        } else {
            super._print(window);
        }
    },
});
