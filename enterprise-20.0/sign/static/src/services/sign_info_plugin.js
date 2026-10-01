import { Plugin, signal, usePlugin } from "@odoo/owl";
import { services } from "@web/core/services";
import { registry } from "@web/core/registry";

export class SignInfoPlugin extends Plugin {
    /** @private */
    signInfo = signal.Object({});

    set(data) {
        Object.assign(this.signInfo(), data);
    }

    reset(data) {
        this.signInfo.set(data);
    }

    get(key) {
        return this.signInfo()[key];
    }
}

services.add(SignInfoPlugin);

/**
 * -----------------------------------------------------------------------------
 * @todo owl3 migration
 * temporary - to remove when all use of the signInfo service are removed
 * -----------------------------------------------------------------------------
 */
export const signInfoService = {
    start() {
        return usePlugin(SignInfoPlugin);
    },
};

registry.category("services").add("signInfo", signInfoService);
