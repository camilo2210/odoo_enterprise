import { patch } from "@web/core/utils/patch";
import { CustomMediaDialog } from "@html_editor/fields/x2many_field/custom_media_dialog";
import { convertAttachmentRecordToObject } from "@ai/core/html_editor/media_dialog/media_dialog_utils";

patch(CustomMediaDialog.prototype, {
    async aiSaveAction({ message }) {
        const imageAttachment = message.attachment_ids.filter((attachment) =>
            attachment.mimetype.includes("image")
        )[0];
        const imageAttachmentObject = convertAttachmentRecordToObject(imageAttachment);
        imageAttachmentObject.mediaType = "attachment";
        await this.props.imageSave([imageAttachmentObject]);
    },
});
