import { Record, fields } from "@mail/model/export";

export class SignRequest extends Record {
    static _name = "sign.request";

    /** @type {number} */
    id;
    create_uid = fields.One("res.users");
    /** @type {boolean} */
    need_my_signature;
    /** @type {string} */
    template_name;
    /** @type {string} */
    signer_names;
    /** @type {Date} */
    validity = fields.Date();
}

SignRequest.register();
