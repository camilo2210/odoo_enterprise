import { fields } from "@mail/model/misc";
import { Record } from "@mail/model/record";

export class Documents extends Record {
    static _name = "documents.document";

    /** @type {string|undefined} */
    display_name;
    name = "";
    user_can_move = "";
    user_folder_id = "";
    attachment_id = fields.One("ir.attachment", { inverse: "document_ids" });
    folder_id = fields.One("documents.document");
}

Documents.register();
