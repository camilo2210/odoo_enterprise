import { patch } from "@web/core/utils/patch";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    async openCashbox(action = false) {
        if (this.config.useFiscalPrinter && !this.data.network.offline) {
            await this.fiscalPrinter.openCashDrawer();
        }
        return super.openCashbox(...arguments);
    },
});
