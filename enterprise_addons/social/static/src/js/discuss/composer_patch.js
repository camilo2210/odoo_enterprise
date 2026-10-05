import { Composer } from "@mail/core/common/composer";
import { patch } from "@web/core/utils/patch";

patch(Composer.prototype, {
    get showComposerAvatarImage() {
        return (
            !this.props.composer.thread.channel?.livechat_social_account_id &&
            super.showComposerAvatarImage
        );
    },
});
