import { ScaleInterface } from "@point_of_sale/app/utils/scale/scale_interface";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class IotScale extends ScaleInterface {
    constructor() {
        super(...arguments);
        this._scaleDevice = this.pos.config.iot_scale_id;
        this.iotHttp = this.env.services.iot_http;
        this.tareEnabled = false;
    }

    get hardwareTare() {
        return this.tareEnabled;
    }

    connectToScale() {
        return Boolean(this._scaleDevice);
    }

    async _readWeight() {
        const { promise, resolve, reject } = Promise.withResolvers();

        const callback = (data) => {
            try {
                resolve(this._handleScaleMessage(data));
            } catch (error) {
                reject(error);
            }
        };

        const { iot_id, identifier } = this._scaleDevice;
        this.iotHttp.action(
            iot_id,
            identifier,
            { action: "read_once", detailed_response: true },
            callback,
            callback
        );

        return promise;
    }

    _handleScaleMessage(data) {
        const status = data.status.status ?? data.status;
        if (status === "error" || status === "timeout") {
            throw new Error(_t("Cannot weigh product - %s", data.status.message_body ?? status));
        } else if (status === "connected" || status === "success") {
            if (typeof data.result === "number") {
                return data.result || 0;
            }
            this.tareEnabled = data.result.tare_mode;
            return data.result.weight || 0;
        }
        return null;
    }
}

registry.category("electronic_scales").add("iot", IotScale);
