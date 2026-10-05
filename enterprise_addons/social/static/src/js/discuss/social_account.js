import { fields, Record } from "@mail/model/export";

export class SocialAccount extends Record {
    static _name = "social.account";

    /** @type {number} */
    id;

    /** @type {string} */
    name;
    media_id = fields.One("social.media");
}

SocialAccount.register();
