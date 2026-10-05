import { Component, signal, useProps, t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { _t } from "@web/core/l10n/translation";
import { logPosMessage } from "@point_of_sale/app/utils/pretty_console_log";

export class OboxDebugPopup extends Component {
    static template = "obox_point_of_sale.OboxDebugPopup";
    static components = { Dialog };
    props = useProps({
        close: t.function(),
    });

    setup() {
        this.pos = usePos();
        this.obox = this.pos.obox;
        this.response = signal(null);
        this.loading = signal(false);
        this.timing = signal(0);
    }

    get proxyPrinters() {
        return this.pos.models["pos.printer"].filter((printer) => printer.proxy_obox_id);
    }

    get baseUrl() {
        return this.pos.config._base_url;
    }

    get receipt() {
        return `
        <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
            <s:Body>
                <epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">
                    <feed line="1" />
                    <text align="center">Test print from OBOX&#10;</text>
                    <feed line="3" />
                    <cut type="feed" />
                </epos-print>
            </s:Body>
        </s:Envelope>`;
    }

    async testPing() {
        return await this.testConnection({
            url: `${this.baseUrl}/obox_point_of_sale/ping`,
            method: "POST",
            payload: { jsonrpc: 2.0, params: {} },
        });
    }

    async testPrint() {
        const printers = this.proxyPrinters;

        if (printers.length === 0) {
            this.pos.notification.add(
                _t("No printer found, please set up a printer to test print functionality."),
                {
                    type: "warning",
                }
            );
            return;
        }
        const printer = printers[0];
        const protocol = printer.use_lna ? "http:" : window.location.protocol;
        const url = protocol + "//" + printer.printer_ip;
        const address = url + "/cgi-bin/epos/service.cgi?devid=local_printer";
        return await this.testConnection({
            method: "POST",
            url: address,
            payload: this.receipt,
        });
    }

    async testConnection(payload) {
        const timingInterval = setInterval(() => {
            this.timing.set(this.timing() + 0.01);
        }, 10);

        this.timing.set(0);
        this.loading.set(true);
        try {
            const obox = this.pos.models["obox.obox"].getFirst();
            const response = await this.obox.createOboxJob({ oboxId: obox.id, payload });
            this.response.set(response[0]);
        } catch (e) {
            this.pos.notification.add(_t("Failed to connect to OBOX, see console for details."), {
                type: "danger",
            });
            logPosMessage(
                "OboxDebugPopup",
                "testConnection",
                `Failed to connect to OBOX: ${e.message}`,
                "#FF0000",
                [e]
            );
        } finally {
            this.loading.set(false);
            clearInterval(timingInterval);
        }
    }
}
