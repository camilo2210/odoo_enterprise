import { saveSingleAttachment } from "@web/core/utils/image_library";

export function product_main_image_action(){
    return async ({ channel, message, store }) => {
        const imageAttachment = message.attachment_ids.filter(attachment => attachment.mimetype.includes('image'))[0];
        await saveSingleAttachment(store.env, {
            attachment: imageAttachment,
            targetRecord: channel.targetRecord,
            targetFieldName: "image_1920",
            changeRecordName: false,
        });
    }
}
