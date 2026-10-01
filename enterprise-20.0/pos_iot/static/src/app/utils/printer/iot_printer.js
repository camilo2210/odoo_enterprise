import { _t } from "@web/core/l10n/translation";
import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { PRINTER_MESSAGES } from "@iot/network_utils/iot_http_service";

/**
 * Used to send print requests to the IoT box using the `iot_http` service.
 */
export class IoTPrinter extends BasePrinter {
    /**
     * @param iotPrinter
     * @param {import("@iot/network_utils/iot_http_service").IotHttpService} iotHttp
     */
    setup({ printer, iotHttp }) {
        super.setup(...arguments);
        this.iotHttp = iotHttp;
        this.device = printer.iot_device_id;
    }

    /**
     * @override
     */
    openCashbox() {
        return this.action({ action: "cashbox" });
    }

    /**
     * @override
     */
    sendPrintingJob(img) {
        return this.action({
            action: "print_receipt",
            receipt: img.toDataURL("image/jpeg").replace("data:image/jpeg;base64,", ""),
        });
    }

    async action(data) {
        return new Promise((resolve) => {
            const processResult = (printResult) => {
                if (printResult.status === "success") {
                    resolve(true);
                }
                resolve({
                    ...printResult,
                    result: false, // used to make the pos call ``getResultsError``
                });
            };

            this.iotHttp.action(
                this.device.iot_id,
                this.device.identifier,
                data,
                processResult,
                processResult
            );
        });
    }

    /**
     * @override
     */
    getActionError() {
        if (window.isSecureContext && this.device.iot_ip?.endsWith(".odoo-iot.com")) {
            return {
                successful: false,
                canRetry: true,
                message: {
                    title: _t("Connection to IoT Box failed"),
                    body: _t(
                        "Your IoT box is registered, but your browser could not reach it.\n" +
                            "Ensure it is powered on and connected to the network.\n\n" +
                            "If you have just paired the IoT box, you may be experiencing a DNS issue.\n" +
                            "If you wait for some time the problem may resolve itself."
                    ),
                },
            };
        }
        return super.getActionError();
    }

    /**
     * @override
     */
    getResultsError(printResult) {
        const title = _t("Printing failed");
        let body;
        switch (printResult.status) {
            case "disconnected":
                body = _t(
                    "The IoT Box is connected, but the receipt printer isn't. In order to continue," +
                        " ensure your printer is connected:\n\n" +
                        "1/ for USB printers, check the cable between the IoT Box and the receipt printer\n" +
                        "2/ for network printers, ensure the printer is connected to the internet."
                );
                break;
            default:
                body = PRINTER_MESSAGES[printResult.message] ?? printResult.message;
                break;
        }
        return {
            successful: false,
            canRetry: true,
            message: { title, body },
        };
    }
}
