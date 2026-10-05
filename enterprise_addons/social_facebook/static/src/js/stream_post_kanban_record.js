import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { StreamPostKanbanRecord } from "@social/js/stream_post_kanban_record";
import { StreamPostCommentsFacebook } from "./stream_post_comments";

import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

patch(StreamPostKanbanRecord.prototype, {
    setup() {
        super.setup(...arguments);

        let likeHandler;

        onMounted(() => {
            const likeEl = this.rootRef().querySelector(".o_social_facebook_likes");
            if (likeEl) {
                likeHandler = this._onFacebookPostLike.bind(this);
                likeEl.addEventListener("click", likeHandler);
            }
        });

        onWillUnmount(() => {
            const likeEl = this.rootRef().querySelector(".o_social_facebook_likes");
            if (likeEl && likeHandler) {
                likeEl.removeEventListener("click", likeHandler);
            }
        });
    },

    openComments(ev) {
        if (this.record.media_type.raw_value !== "facebook") {
            return super.openComments(ev);
        }
        ev.stopPropagation();
        const postId = this.record.id.raw_value;
        rpc("/social_facebook/get_comments", {
            stream_post_id: postId,
            comments_count: this.commentsCount,
        }).then((result) => {
            this.dialog.add(StreamPostCommentsFacebook, {
                title: _t("Facebook Comments"),
                accountId: this.record.account_id.raw_value,
                originalPost: this.props.record,
                commentsCount: this.commentsCount,
                postId: postId,
                comments: result.comments,
                summary: result.summary,
                nextRecordsToken: result.nextRecordsToken,
                onFacebookPostLike: this._onFacebookPostLike.bind(this),
            });
        });
    },

    async _onFacebookPostLike() {
        const userLikes = this.record.facebook_user_likes.raw_value;
        await rpc("/social_facebook/like_post", {
            stream_post_id: this.record.id.raw_value,
            like: !userLikes,
        });
        await this.props.record.load();
    },
});
