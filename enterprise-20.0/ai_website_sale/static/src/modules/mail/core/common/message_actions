import { _t } from "@web/core/l10n/translation";
import { registerMessageAction } from "@mail/core/common/message_actions";
import { AIMessageActions } from "@ai/discuss/message_actions_patch";

AIMessageActions.push('product_extra_image');

registerMessageAction('product_extra_image', {
    condition: ({ message, channel }) => {
        return !!channel?.aiSpecialActions?.product_extra_image
        && !message.isSelfAuthored
        && !!message.attachment_ids.filter(attachment => attachment.mimetype.includes('image')).length
    },
    name: _t("Extra Photo"),
    onSelected: ({ channel, ...args }) => channel.aiSpecialActions.product_extra_image({ channel, ...args }),
    sequence: 10,
});
