import { Record, fields } from "@mail/model/export";

export class AiAgent extends Record {
    static _name = "ai.agent";

    /** @type {number} */
    id;
    partner_id = fields.One("res.partner");
    /** @type {string} */
    name;
    sources_ids = undefined;
    /** @type {string} */
    subtitle;
    xml_id;
}

AiAgent.register();
