import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);

        onMounted(async () => {
            if (this.pos.config.useFiscalPrinter) {
                let fiscalPrinter = await this.pos.ticketPrinter.selectPrinter();
                if (!fiscalPrinter) {
                    fiscalPrinter = this.pos.ticketPrinter.receiptPrinters.find(
                        (printer) => printer.printer_type === "it_fiscal_printer"
                    );
                    this.pos.ticketPrinter.defaultPrinter = fiscalPrinter;
                }
                this.pos.ticketPrinter.fiscalPrinter.getPrinterSerialNumber().then((sn) => {
                    this.pos.config.it_fiscal_printer_serial_number = sn;
                });
            }
        });
    },
});
