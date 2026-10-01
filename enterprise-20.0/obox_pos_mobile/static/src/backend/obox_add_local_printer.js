import { Component, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { hasMobileNative, mobileNative } from "@pos_mobile_android/app/utils/native";

export function localPrinterDomain(serialNumber) {
    const domain = [["type", "=", "printer"]];
    const serial = serialNumber?.trim().toUpperCase();
    if (serial) {
        domain.push(["obox_id.serial_number", "=", serial]);
    }
    return domain;
}

function waitForReturn() {
    return new Promise((resolve) => {
        const onVisibilityChange = () => {
            if (document.visibilityState === "visible") {
                document.removeEventListener("visibilitychange", onVisibilityChange);
                resolve();
            }
        };
        document.addEventListener("visibilitychange", onVisibilityChange);
    });
}

export class OboxAddLocalPrinter extends Component {
    static template = "obox_pos_mobile.OboxAddLocalPrinter";
    props = useProps(standardWidgetProps);

    setup() {
        super.setup();
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.available = hasMobileNative("openDeviceManager");
    }

    async addLocalPrinter() {
        try {
            const returned = waitForReturn();
            await mobileNative.openDeviceManager({
                url: browser.location.origin,
                return_when_done: true,
            });
            await returned;
        } catch {
            this.notification.add(_t("Could not open the device manager"), { type: "danger" });
            return;
        }
        await this.selectLocalPrinter();
    }

    // Select the last printer that was added to the device manager for the current obox, if any.
    async selectLocalPrinter() {
        const record = this.props.record;
        if (record.data.obox_device_id) {
            return;
        }
        const serialNumber = await this.getLocalSerialNumber();
        const printer = serialNumber && (await this.findLastPrinter(serialNumber));
        if (printer) {
            await record.update({
                obox_device_id: { id: printer.id, display_name: printer.display_name },
            });
        }
    }

    async findLastPrinter(serialNumber) {
        const { records } = await this.orm.webSearchRead(
            "obox.device",
            localPrinterDomain(serialNumber),
            { specification: { display_name: {} }, order: "id desc", limit: 1 }
        );
        return records[0];
    }

    async getLocalSerialNumber() {
        if (!hasMobileNative("getDeviceManagerStatus")) {
            return null;
        }
        try {
            return (await mobileNative.getDeviceManagerStatus()).serial;
        } catch {
            return null;
        }
    }
}

registry.category("view_widgets").add("obox_add_local_printer", { component: OboxAddLocalPrinter });
