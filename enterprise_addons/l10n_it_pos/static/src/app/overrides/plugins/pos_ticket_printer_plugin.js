import { patch } from "@web/core/utils/patch";
import { EpsonFiscalPrinter } from "../../fiscal_printer/epson_fiscal_printer";
import { PosTicketPrinterPlugin } from "@point_of_sale/app/plugins/pos_ticket_printer_plugin";

patch(PosTicketPrinterPlugin.prototype, {
    get fiscalPrinter() {
        return this.defaultPrinter?._instance;
    },
    async createPrinterInstance(printer) {
        if (printer.printer_type === "it_fiscal_printer") {
            return new EpsonFiscalPrinter(!printer.use_lna, printer.printer_ip, this, this.dialog);
        }

        return await super.createPrinterInstance(...arguments);
    },
    async printOrderReceipt({
        basic = false,
        order = this.getOrder(),
        printBillActionTriggered = false,
    } = {}) {
        if (!this.config.useFiscalPrinter) {
            return super.printOrderReceipt(...arguments);
        }
        const isFiscal = !basic && !printBillActionTriggered;
        let result = {};

        if (!isFiscal) {
            await this.fiscalPrinter.printNonFiscalReceipt({
                order: order,
                isBasicPrint: basic,
                isEarlyPrint: printBillActionTriggered,
            });
        } else if (!order.nb_print) {
            try {
                result = order.to_invoice
                    ? await this.fiscalPrinter.printFiscalInvoice({ order })
                    : await this.fiscalPrinter.printFiscalReceipt({ order });
            } catch (error) {
                result.success = false;
                if (!this.data.network.offline) {
                    throw error;
                }
            }

            if (result.success) {
                this.data.write("pos.order", [order.id], {
                    it_fiscal_receipt_number: result.addInfo.fiscalReceiptNumber,
                    it_fiscal_receipt_date: result.addInfo.fiscalReceiptDate,
                    it_z_rep_number: result.addInfo.zRepNumber,
                    //update the number of times the order got printed, handling undefined
                    nb_print: order.nb_print ? order.nb_print + 1 : 1,
                });
                if (this.config.useFiscalPrinter) {
                    await this.fiscalPrinter.openCashDrawer();
                }
                return true;
            }
        } else {
            this.fiscalPrinter.printContentByNumbers({
                order: order,
            });
        }
    },
});
