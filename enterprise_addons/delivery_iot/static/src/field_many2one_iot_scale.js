import { Component, onWillUnmount, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { computeM2OProps, Many2One } from "@web/views/fields/many2one/many2one";
import {
    buildM2OFieldDescription,
    many2OneFieldProps,
} from "@web/views/fields/many2one/many2one_field";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class FieldMany2OneIoTScale extends Component {
    static template = "delivery_iot.FieldMany2OneIoTScale";
    static components = { Many2One };
    props = useProps({ ...many2OneFieldProps });

    setup() {
        this.iotHttpService = useService("iot_http");
        this.notification = useService("notification");

        this.onClickReadWeight(); // Send a first action to set the `session_id`
        onWillUnmount(() => (this._isMeasuring = false));
    }

    get iotDevice() {
        const deviceId = this.props.record.data;
        if (!deviceId.iot_id || !deviceId.device_identifier) {
            return false;
        }
        return {
            iotBoxId: deviceId.iot_id,
            deviceIdentifier: deviceId.device_identifier,
        };
    }

    _keepMeasuring() {
        if (!this._isMeasuring) {
            return;
        }
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.onMessage(
            iotBoxId,
            deviceIdentifier,
            (e) => this.onSuccess(e.result),
            this.notifyFailure.bind(this)
        );
    }

    notifyFailure() {
        this._isMeasuring = false;
        this.notification.add(_t("Could not get measurement from device"), {
            type: "danger",
        });
    }

    async onSuccess(result) {
        if (!this._isMeasuring) {
            return;
        }
        if (!result) {
            return this.notifyFailure();
        }
        this._keepMeasuring();
        this.props.record.update({ shipping_weight: result });
    }

    get m2oProps() {
        return computeM2OProps(this.props);
    }

    onClickReadWeight() {
        if (!this.iotDevice) {
            this.notification.add(_t("No IoT device configured."), {
                type: "warning",
            });
            return;
        }
        const { iotBoxId, deviceIdentifier } = this.iotDevice;
        this.iotHttpService.action(
            iotBoxId,
            deviceIdentifier,
            { action: "read_once" },
            (e) => this.onSuccess(e.result),
            this.notifyFailure.bind(this)
        );
        this._isMeasuring = true;
        this._keepMeasuring();
    }
}

registry
    .category("fields")
    .add("field_many2one_iot_scale", buildM2OFieldDescription(FieldMany2OneIoTScale));
