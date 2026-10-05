import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    async printOrderReceipt({ order } = {}) {
        if (order.useBlackBoxSweden()) {
            if (order) {
                if (order.nb_print > 1) {
                    this.dialog.add(AlertDialog, {
                        title: _t("Oh snap !"),
                        body: _t("A receipt can only be printed once."),
                    });
                    return;
                }
                if (order.nb_print === 1) {
                    order.receipt_type = "kopia";
                    await this.pos.pushSingleOrder(order);
                    order.receipt_type = false;
                    order.isReprint = true;
                }
                return super.printOrderReceipt(...arguments);
            }
        } else {
            return super.printOrderReceipt(...arguments);
        }
    },
});
