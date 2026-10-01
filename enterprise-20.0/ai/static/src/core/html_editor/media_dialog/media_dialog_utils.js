import { ATTACHMENT_FIELDS } from "@html_editor/main/media/media_dialog/file_selector";

export function convertAttachmentRecordToObject(attachment_record) {
    const imageAttachmentObject = {};
    for (const attachment_field of ATTACHMENT_FIELDS) {
        imageAttachmentObject[attachment_field] = attachment_record[attachment_field];
    }
    return imageAttachmentObject;
}
