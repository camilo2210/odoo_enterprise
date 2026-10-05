import { _t } from "@web/core/l10n/translation";
import { registry } from '@web/core/registry';
import { onWillUnmount } from "@odoo/owl";
import { IotActionButton } from "./iot_action_button/iot_action_button";

export class IotMeasureWidget extends IotActionButton {
    setup() {
        super.setup();
        this.onClick(); // Send a first action to set the `session_id`
        onWillUnmount(() => this._isMeasuring = false);
    }

    _keepMeasuring() {
        if (!this._isMeasuring) {
            return;
        }
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.onMessage(
            iotBoxId,
            deviceIdentifier,
            this.onSuccess.bind(this),
            this.notifyFailure.bind(this)
        );
    }

    onClick() {
        if (!this.iotDevice) {
            this.notification.add(_t("No IoT device configured for this quality check."), {
                type: "warning",
            });
            return;
        }
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.action(
            iotBoxId,
            deviceIdentifier,
            { action: 'read_once' },
            this.onSuccess.bind(this),
            this.notifyFailure.bind(this)
        );
        this._isMeasuring = true;
        this._keepMeasuring()
    }

    notifyFailure() {
        this._isMeasuring = false;
        this.notification.add(_t('Could not get measurement from device'), {
            type: 'danger',
        });
    }

    async onSuccess(data) {
        const measure = data.result ? data.result : data.value; // calipers still send in `value` key
        if (!measure) {
            return this.notifyFailure();
        }
        this._keepMeasuring();
        this.props.record.update({ measure });
    }
}

registry.category("view_widgets").add("iot_measure", {
    component: IotMeasureWidget,
    extractProps: ({ attrs }) => {
        return { btn_name: attrs.btn_name };
    },
});
