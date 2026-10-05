import { Plugin, signal } from "@odoo/owl";

export class auditBalanceListChatterPlugin extends Plugin {
    res_id = signal(undefined);
    date_to = signal(undefined);

    closeChatter() {
        this.res_id.set(undefined);
    }

    openChatter(resId) {
        this.res_id.set(resId);
    }
}
