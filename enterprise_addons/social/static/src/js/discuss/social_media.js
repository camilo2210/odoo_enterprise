import { Record } from "@mail/model/export";

export class SocialMedia extends Record {
    static _name = "social.media";

    /** @type {number} */
    id;
}

SocialMedia.register();
