import { Record } from "@mail/model/export";

export class SignTemplate extends Record {
    static _name = "sign.template";

    /** @type {number} */
    id;
    /** @type {string} */
    name;
}

SignTemplate.register();
