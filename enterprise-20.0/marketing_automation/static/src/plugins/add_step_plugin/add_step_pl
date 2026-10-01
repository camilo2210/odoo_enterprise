import { Plugin } from "@odoo/owl";
import { services } from "@web/core/services";

export class MarketingAutomationAddStepPlugin extends Plugin {
    /** @param {function} */
    add(callback) {
        this.callback = callback;
    }

    delete() {
        delete this.callback;
    }

    /** @param {Object} record */
    async execute(record) {
        const res = (await this.callback?.(record)) ?? false;
        this.delete();
        return res;
    }
}

services.add(MarketingAutomationAddStepPlugin);
