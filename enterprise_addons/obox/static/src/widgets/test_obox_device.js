import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatFloat } from "@web/core/utils/numbers";
import { Component, useProps, proxy } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { SelectMenu } from "@web/core/select_menu/select_menu";
import { getDataURLFromFile } from "@web/core/utils/urls";

export class TestOboxDevice extends Component {
    static template = "obox.TestOboxDevice";
    static components = { SelectMenu };
    props = useProps(standardWidgetProps);

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.state = proxy({ loading: false, printType: null });
        this.fileViewer = useFileViewer();
    }

    get device() {
        return this.props.record.data;
    }

    get testPrintOptions() {
        return [
            { value: "pdf", label: _t("PDF report") },
            { value: "zpl", label: _t("ZPL label") },
            { value: "epos", label: _t("Receipt") },
        ];
    }

    async testPrintData() {
        switch (this.state.printType) {
            case "zpl": {
                return btoa("^XA^FO50,50^ADN,36,20^FDTest ZPL label^FS^XZ");
            }
            case "epos": {
                return `
                    <s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
                        <s:Body>
                            <epos-print xmlns="http://www.epson-pos.com/schemas/2011/03/epos-print">
                                <feed line="1" />
                                <text align="center">Test print for printer ${this.device.name}&#10;</text>
                                <feed line="3" />
                                <cut type="feed" />
                            </epos-print>
                        </s:Body>
                    </s:Envelope>
                `;
            }
            case "pdf": {
                const body = new FormData();
                body.append("csrf_token", odoo.csrf_token);
                body.append(
                    "data",
                    JSON.stringify(["/report/pdf/web.preview_externalreport", "qweb-pdf"])
                );
                const response = await browser.fetch("/report/download", {
                    method: "POST",
                    body,
                });
                const blob = await response.blob();
                const dataUrl = await getDataURLFromFile(blob);
                return dataUrl.replace(/data:.*,/, "");
            }
        }
    }

    onPrintTypeSelected(printType) {
        this.state.printType = printType;
    }

    async testScale() {
        const response = await browser.fetch(
            `http://${this.device.local_ip}/usb/v1/scale/read_scale_weight`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                targetAddressSpace: "local",
                body: JSON.stringify({ identifier: this.device.identifier }),
            }
        );
        const result = await response.json();
        if (result.weight != null) {
            this.notification.add(
                _t("Scale reads %skg", formatFloat(result.weight, { minDigits: 3 })),
                {
                    type: "success",
                }
            );
        } else {
            this.notification.add(_t("Error reading scale: %s", result.error), { type: "danger" });
        }
    }

    async testCamera() {
        const response = await browser.fetch(
            `http://${this.device.local_ip}/usb/v1/camera/take-picture?identifier=${this.device.identifier}`,
            {
                targetAddressSpace: "local",
            }
        );
        const result = await response.json();
        if (result.image) {
            const imageDataUrl = "data:image/jpeg;base64," + result.image;
            this.fileViewer.open({
                name: "image.jpg",
                downloadUrl: imageDataUrl,
                defaultSource: imageDataUrl,
                isViewable: true,
                isImage: true,
            });
        } else {
            this.notification.add(_t("Error taking photo: %s", result.error), { type: "danger" });
        }
    }

    async testPrinter() {
        const printData = await this.testPrintData();
        if (this.state.printType === "epos") {
            await browser.fetch(
                `http://${this.device.local_ip}/usb/v1/printer/${this.device.identifier}/cgi-bin/epos/service.cgi`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/xml" },
                    targetAddressSpace: "local",
                    body: printData,
                }
            );
        } else {
            await this.orm.create("obox.queue", [
                {
                    action_type: "action",
                    obox_id: this.device.obox_id.id,
                    payload: {
                        url: "/usb/v1/printer/print",
                        payload: { identifier: this.device.identifier, document: printData },
                        method: "POST",
                    },
                },
            ]);
        }
        this.notification.add(_t("Test print successful"), {
            type: "success",
        });
    }

    async onClick() {
        this.state.loading = true;
        try {
            switch (this.device.type) {
                case "printer": {
                    await this.testPrinter();
                    break;
                }
                case "scale": {
                    await this.testScale();
                    break;
                }
                case "camera": {
                    await this.testCamera();
                    break;
                }
            }
        } catch (error) {
            console.error(error);
            this.notification.add(_t("Failed to reach device"), { type: "danger" });
        }

        this.state.loading = false;
    }
}

registry.category("view_widgets").add("test_obox_device", {
    component: TestOboxDevice,
});
