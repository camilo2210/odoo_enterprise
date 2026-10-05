import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { QualityCheck } from "@mrp_workorder/mrp_display/mrp_record_line/quality_check";
import { Component, useProps, t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class IotPicturePreview extends Component {
    static components = { Dialog };
    static template = "mrp_iot.ImagePreviewDialog";
    props = useProps({
        src: t.string(),
        close: t.function(),
    });
}

patch(QualityCheck.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.iotHttpService = useService("iot_http");
    },
    get iotDevice() {
        return {
            iotBoxId: this.props.record.data.iot_box_id.id,
            deviceIdentifier: this.props.record.data.identifier,
        };
    },
    /** override the quality check click behavior to capture image from an IoT camera */
    async clicked() {
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        if (
            !["picture", "measure"].includes(this.type) ||
                !iotBoxId ||
                !deviceIdentifier
        ) {
            return super.clicked();
        }
        if (this.type === "picture") {
            this.notification.add(_t("Capturing image..."));
            this._sendIotAction({}, this.iotUpdatePicture.bind(this));
        } else if (this.type === "measure") {
            this.notification.add(_t("Getting measurement..."));
            this._sendIotAction({ action: "read_once" }, this.iotUpdateMeasurement.bind(this));
        }
    },
    _sendIotAction(action, onSuccess) {
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.action(
            iotBoxId,
            deviceIdentifier,
            action,
            onSuccess,
            this._notifyFailure.bind(this)
        );
    },
    _notifyFailure(data) {
        if (data.status === "disconnected") {
            this.notification.add(_t("Please ensure the device is correctly connected."), {
                type: "danger",
            });
            return;
        }
        this.notification.add(_t("Failed to communicate with the device. Please try again."), {
            type: "danger",
        });
    },
    async iotUpdatePicture(data) {
        if (!data.result?.image) {
            return this._notifyFailure();
        }
        this.notification.add(_t("Image captured successfully"), { type: "success" });
        const imageBase64 = data.result?.image;
        await this.onFileUploaded({ data: imageBase64 });
        this.dialog.add(IotPicturePreview, { src: this.imageUrl });
    },
    async iotUpdateMeasurement(data) {
        if (data.value === undefined || data.value === null) {
            return this._notifyFailure();
        }
        await this.props.record.update({ measure: data.value });
        super.clicked();
    },
});
