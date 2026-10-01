import { Reactive } from "@web/core/utils/reactive";
import { parseXML } from "@web/core/utils/xml";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { htmlToXml } from "@l10n_it_pos/app/utils/html_to_xml";
import { _t } from "@web/core/l10n/translation";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";
import {
    FiscalReceipt,
    FiscalInvoice,
    XReport,
    ZReport,
    XZReport,
} from "@l10n_it_pos/app/documents";
import {
    PrintDuplicateReceipt,
    PrintContentByNumbers,
    DisplayText,
    OpenDrawer,
    RTStatus,
    DirectIO,
} from "@l10n_it_pos/app/fiscal_printer/commands";

const DEFAULT_TIMEOUT = 10000;
const DEFAULT_DEVID = "local_printer";
const tags = [
    "printerFiscalReceipt",
    "displayText",
    "printRecMessage",
    "beginFiscalReceipt",
    "printRecItem",
    "printRecItemAdjustment",
    "printRecSubtotalAdjustment",
    "printRecSubtotal",
    "printBarCode",
    "printRecTotal",
    "endFiscalReceipt",
    "printerFiscalDocument",
    "beginFiscalDocument",
    "endFiscalDocument",
    "printerCommand",
    "queryPrinterStatus",
    "printerFiscalReport",
    "printXReport",
    "printXZReport",
    "printZReport",
    "setLogo",
    "printRecRefund",
    "directIO",
    "printDuplicateReceipt",
    "openDrawer",
    "printContentByNumbers",
    "printerNonFiscal",
    "printNormal",
    "beginNonFiscal",
    "endNonFiscal",
];

const attributes = [
    "messageType",
    "unitPrice",
    "adjustmentType",
    "paymentType",
    "hRIPosition",
    "hRIFont",
    "codeType",
    "documentType",
    "documentNumber",
    "graphicFormat",
    "statusType",
    "fromNumber",
    "toNumber",
];

const CONSOLE_COLOR = "#5425ff";

class Command extends String {
    toXML(indentation = "  ") {
        const reg = /(>)(<)(\/*)/g;
        const formatted = this.replace(reg, "$1\r\n$2$3");
        const lines = formatted.split("\r\n");

        let indent = "";
        const formattedLines = [];
        for (const line of lines) {
            if (/^<\/\w/.test(line)) {
                // Decrease indent for closing elements.
                indent = indent.substring(indentation.length);
            }

            const indentedLine = indent + line;

            if (
                /<\w[^>]*[^/]>.*$/ /// Tag opening
                    .test(line)
            ) {
                indent += indentation; // Increase indent after an opening tag.
            }

            formattedLines.push(indentedLine);
        }

        return formattedLines.join("\r\n");
    }
}

export class EpsonFiscalPrinter extends Reactive {
    constructor() {
        super(...arguments);
        this.setup(...arguments);
    }
    setup(isHttps, ip, ticketPrinter, dialog) {
        // workaround for duplicate receipt printing
        // the italian printer IP can have the special form my_fiscal_printer_ip?login=xxxxx
        // if the user ever modified the printer login (12345 by default)
        const [baseIp, query = ""] = ip.split("?");
        const prefix = "login=";

        this.ip = baseIp;
        this.query = query;
        this.login = query.startsWith(prefix) ? query.slice(prefix.length) : "12345";
        this.use_lna = !isHttps;
        this.dialog = dialog;
        this.ticketPrinter = ticketPrinter;
    }

    removeUnsupportedChars(str) {
        return str.replace(/[åÅæÆ¢¥₧ƒªº¿⌐¬¡αßΓπΣσµτΘΩδ∞ε∩≡±⌠⌡∙·√ⁿ²]/g, " ").replace(/&nbsp;/g, " "); // Remove non-breaking space
    }

    async command(component, props = {}) {
        const html = await this.ticketPrinter.getHtmlFromComponent(component, props);
        const xmlString = htmlToXml(html, tags, attributes);
        const command =
            '<?xml version="1.0" encoding="utf-8"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>' +
            xmlString +
            "</s:Body></s:Envelope>";

        return new Command(this.removeUnsupportedChars(command));
    }

    async printFiscalReceipt({ timeout, devid, order } = {}) {
        const command = await this.command(FiscalReceipt, { order });
        return this.sendCommand(command, { timeout, devid });
    }

    async printNonFiscalReceipt({ timeout, devid, order, isBasicPrint, isEarlyPrint } = {}) {
        const command = await this.command(FiscalReceipt, {
            order,
            isFiscal: false,
            isBasicPrint: isBasicPrint,
            isEarlyPrint: isEarlyPrint,
        });
        return this.sendCommand(command, { timeout, devid });
    }

    async printFiscalInvoice({ timeout, devid, order } = {}) {
        const command = await this.command(FiscalInvoice, { order });
        return this.sendCommand(command, { timeout, devid });
    }

    async printXReport({ timeout, devid } = {}) {
        const command = await this.command(XReport);
        return this.sendCommand(command, { timeout, devid });
    }

    async printZReport({ timeout, devid } = {}) {
        const command = await this.command(ZReport);
        return this.sendCommand(command, { timeout, devid });
    }

    async printXZReport({ timeout, devid } = {}) {
        const command = await this.command(XZReport);
        return this.sendCommand(command, { timeout, devid });
    }

    async getRTStatus({ timeout, devid } = {}) {
        const command = await this.command(RTStatus);
        return this.sendCommand(command, { timeout, devid });
    }

    async displayText(message, { timeout, devid } = {}) {
        const command = await this.command(DisplayText, { message });
        return this.sendCommand(command, { timeout, devid });
    }

    async printDuplicateReceipt({ timeout, devid } = {}) {
        const command = await this.command(PrintDuplicateReceipt);
        return this.sendCommand(command, { timeout, devid });
    }

    async openCashDrawer({ timeout, devid } = {}) {
        const command = await this.command(OpenDrawer);
        return this.sendCommand(command, { timeout, devid });
    }

    async directIO(cmd, data, { timeout, devid } = {}) {
        const command = await this.command(DirectIO, { command: cmd, data });
        return this.sendCommand(command, { timeout, devid });
    }

    async getPrinterSerialNumber() {
        const result = await this.directIO("3217", "01");
        if (!result.success) {
            return null;
        }

        return result.addInfo.responseData;
    }

    /*
     * In theory, the printer command can reprint any number of receipts.
     * We decide that we will only use it to reprint the one receipt selected by the user.
     * This moves the complexity of parsing date strings and ranges to the command component and
     * therefore will keep the rest of the code cleaner
     */
    async printContentByNumbers({ timeout, devid, order } = {}) {
        // must be logged in to print fiscal data :facepalm:
        // magic prepend "02" and pad to 100 comes from the documentation
        let passwordParam = "02" + this.login;
        passwordParam = passwordParam.padEnd(100, " ");
        await this.directIO("4038", passwordParam);

        //once logged in, actually do the print
        const command = await this.command(PrintContentByNumbers, { order: order });
        return this.sendCommand(command, { timeout, devid });
    }

    async sendCommand(command, { timeout, devid } = {}) {
        logPosMessage("EpsonFiscalPrinter", "sendCommand", "Sending command", CONSOLE_COLOR, [
            command.toXML(),
        ]);

        try {
            const url = this._getUrl({ timeout, devid });
            const params = {
                method: "POST",
                signal: AbortSignal.timeout(3000),
                headers: {
                    "Content-Type": "text/xml; charset=utf-8",
                    "Content-Length": command.length,
                    "If-Modified-Since": "Thu, 01 Jan 1970 00:00:00 GMT",
                },
                body: command,
            };

            if (this.use_lna) {
                params.targetAddressSpace = "local";
            }

            const response = await fetch(url, params);
            if (response.status === 200) {
                const xml = await response.text();
                const parsed = parseXML(xml);
                const result = parsed.children[0].children[0];
                const success = result.attributes["success"].value === "true";
                const code = result.attributes["code"].value;
                const status = result.attributes["status"].value;

                if (!success) {
                    logPosMessage(
                        "EpsonFiscalPrinter",
                        "sendCommand",
                        `Command failed with code ${code} and status ${status}`,
                        false,
                        [result]
                    );
                    this.dialog.add(AlertDialog, {
                        title: _t("Fiscal Printer Error"),
                        body: `CODE: ${code}\nSTATUS: ${status}`,
                    });
                }

                const addInfo = {};
                for (const child of result.children[0].children) {
                    if (child.tagName in addInfo) {
                        addInfo[child.tagName] = [addInfo[child.tagName]];
                        addInfo[child.tagName].push(child.textContent);
                    } else {
                        addInfo[child.tagName] = child.textContent;
                    }
                }
                // remove elementList
                delete addInfo.elementList;
                return { success, code, status, addInfo };
            }
        } catch {
            this.dialog.add(AlertDialog, {
                title: _t("Fiscal Printer Connection Error"),
                body: _t(
                    "Could not connect to the fiscal printer. Please check the printer is powered on and connected to the network."
                ),
            });

            return { success: false, code: "CONNECTION_ERROR", status: 0 };
        }
    }

    _getUrl({ timeout, devid }) {
        const protocol = this.use_lna ? "http" : "https";
        const id = devid || DEFAULT_DEVID;
        const timeo = timeout || DEFAULT_TIMEOUT;
        return `${protocol}://${this.ip}/cgi-bin/fpmate.cgi?devid=${id}&timeout=${timeo}`;
    }
}
