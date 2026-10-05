import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { QualityCheck } from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";
import { Component, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { browser } from "@web/core/browser/browser";

export class IotPicturePreview extends Component {
    static components = { Dialog };
    static template = "obox_mrp.ImagePreviewDialog";

    props = useProps({
        src: t.string(),
        close: t.function(),
    });
}

patch(QualityCheck.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
    },
    get address() {
        const { obox_ip } = this.props.record.data;
        if (!obox_ip) {
            return false;
        }
        return `http://${obox_ip}/usb/v1`;
    },
    get identifier() {
        return this.props.record.data.obox_device_identifier ?? false;
    },
    /** override the quality check click behavior to capture image from an IoT camera */
    async clicked() {
        if (!["picture", "measure"].includes(this.type) || !this.address || !this.identifier) {
            return super.clicked();
        }
        if (this.type === "picture") {
            this.notification.add(_t("Capturing image..."));
            await this.takePicture();
        } else if (this.type === "measure") {
            this.notification.add(_t("Getting measurement..."));
            await this.takeMeasure();
        }
    },
    async fetchDevice(url, options, errorMessage) {
        let result;
        try {
            const response = await browser.fetch(url, { targetAddressSpace: "local", ...options });
            result = await response.json();
        } catch {
            this.notification.add(errorMessage, { type: "danger" });
            return;
        }
        return result;
    },
    async takePicture() {
        const result = await this.fetchDevice(
            `${this.address}/camera/take-picture?identifier=${this.identifier}`,
            {},
            _t("Could not capture image.")
        );
        if (!result) {
            return;
        }
        if (!result.image) {
            this.notification.add(result?.error ?? JSON.stringify(result), { type: "danger" });
            return;
        }
        this.notification.add(_t("Image captured successfully"), { type: "success" });
        await this.onFileUploaded({ data: result.image });
        this.dialog.add(IotPicturePreview, { src: this.imageUrl });
    },
    async takeMeasure() {
        const result = await this.fetchDevice(
            `${this.address}/scale/read_scale_weight`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ identifier: this.identifier, fake: 1 }),
            },
            _t("Could not get weight.")
        );
        if (!result) {
            return;
        }
        if (!result.weight) {
            this.notification.add(result?.error ?? JSON.stringify(result), { type: "danger" });
            return;
        }
        await this.props.record.update({ measure: result.weight });
        super.clicked();
    },
});
