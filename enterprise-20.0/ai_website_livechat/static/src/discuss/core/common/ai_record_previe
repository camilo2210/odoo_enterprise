import { fields, Record } from "@mail/model/export";

/**
 * @typedef {{
 *  preview_key: number,
 *  model: string,
 *  records: { id: number, name: string, url: string}[],
 *  header: string,
 *  has_preview_cards: boolean,
 * }} PreviewSet
 */

export class AIRecordPreviewsData extends Record {
    static _name = "ai.record.previews";
    static id = "message_id";

    message_id = fields.One("mail.message", { inverse: "ai_record_previews" });
    /** @type {PreviewSet[]} */
    preview_sets = [];
}

AIRecordPreviewsData.register();
