import { ScaleInterface } from "@point_of_sale/app/utils/scale/scale_interface";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";

export class OboxScale extends ScaleInterface {
    constructor() {
        super(...arguments);
        this._scaleDevice = this.pos.config.obox_scale_id;
    }

    get address() {
        return `http://${this._scaleDevice.obox_id.local_ip}`;
    }

    connectToScale() {
        return Boolean(this._scaleDevice);
    }

    async _readWeight() {
        let result;
        try {
            const response = await browser.fetch(this.address + "/usb/v1/scale/read_scale_weight", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                targetAddressSpace: "local",
                body: JSON.stringify({ identifier: this._scaleDevice.identifier }),
            });
            result = await response.json();
        } catch (e) {
            throw new Error(_t("Cannot weigh product - %s", e));
        }
        if (!result?.weight) {
            throw new Error(result?.error ?? JSON.stringify(result));
        }
        return result.weight;
    }
}

registry.category("electronic_scales").add("obox", OboxScale);
