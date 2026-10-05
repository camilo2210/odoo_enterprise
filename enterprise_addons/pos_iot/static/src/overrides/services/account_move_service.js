import { patch } from "@web/core/utils/patch";
import { accountMoveService, AccountMoveService } from "@account/services/account_move_service";
import { uuidv4 } from "@point_of_sale/utils";

patch(AccountMoveService.prototype, {
    setup(env, services) {
        super.setup(...arguments);
        this.iotHttp = services.iot_http;
        this.printersCache = services.report_printers_cache;
    },

    async downloadPdf(accountMoveId) {
        const [invoiceReport] = await this.orm.searchRead(
            "ir.actions.report",
            [["report_name", "=", "account.report_invoice_with_payments"]],
            ["id", "printer_ids"]
        );
        if (!invoiceReport?.printer_ids?.filter((p) => p.type === "iot").length) {
            return super.downloadPdf(...arguments);
        }

        const printerSettings = await this.printersCache.getPrinterSettingsForReport(
            invoiceReport.id
        );
        if (!printerSettings?.selectedPrinters) {
            return super.downloadPdf(...arguments);
        }

        const downloadAction = await this.orm.call("account.move", "action_invoice_download_pdf", [
            accountMoveId,
        ]);
        const pdfResponse = await fetch(downloadAction.url);
        const pdfBytes = new Uint8Array(await pdfResponse.arrayBuffer());
        const pdfByteString = pdfBytes.reduce(
            (currentString, nextByte) => (currentString += String.fromCharCode(nextByte)),
            ""
        );
        const base64String = btoa(pdfByteString);

        for (const printerDevice of printerSettings.selectedPrinters) {
            await this.iotHttp.action(printerDevice.iot_id, printerDevice.identifier, {
                document: base64String,
                duplex: printerSettings.duplex,
                print_id: uuidv4(),
            });
        }
    },
});

patch(accountMoveService, {
    dependencies: [...accountMoveService.dependencies, "report_printers_cache", "iot_http"],
});
