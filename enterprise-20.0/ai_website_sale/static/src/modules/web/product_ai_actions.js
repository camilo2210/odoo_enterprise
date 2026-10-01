import { saveMultipleAttachments } from "@web/core/utils/image_library";

export function product_extra_image_action(){
    return async ({ channel, message, store }) => {
        const imageAttachment = message.attachment_ids.filter(attachment => attachment.mimetype.includes('image'))[0];
        await saveMultipleAttachments(store.env, {
            attachments: [imageAttachment],
            targetRecord: channel.targetRecord,
            targetFieldName: "product_template_image_ids",
            convertToWebp: true,
        });
    }
}
