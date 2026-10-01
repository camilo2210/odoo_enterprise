import { Record } from "@mail/model/export";

export class WhatsAppAccount extends Record {
    static _name = "whatsapp.account";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
}

WhatsAppAccount.register();
