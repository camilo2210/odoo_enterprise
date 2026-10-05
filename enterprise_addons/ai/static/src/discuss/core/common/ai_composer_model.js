import { Record } from "@mail/model/export";

export class AiComposer extends Record {
    static _name = "ai.composer";

    /** @type {number} */
    id;
    /** @type {string} */
    interface_key;
}

AiComposer.register();
