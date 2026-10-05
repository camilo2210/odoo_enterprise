import { Record } from "@mail/model/export";
import { router } from "@web/core/browser/router";

export class HelpdeskTicket extends Record {
    static _name = "helpdesk.ticket";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
    href = this.computed(() => router.stateToUrl({ model: "helpdesk.ticket", resId: this.id }));
}

HelpdeskTicket.register();
