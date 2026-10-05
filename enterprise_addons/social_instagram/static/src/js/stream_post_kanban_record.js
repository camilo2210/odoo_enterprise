import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { StreamPostKanbanRecord } from '@social/js/stream_post_kanban_record';
import { StreamPostCommentsInstagram } from './stream_post_comments';

import { patch } from "@web/core/utils/patch";

patch(StreamPostKanbanRecord.prototype, {

    setup() {
        super.setup(...arguments);
    },

    openComments(ev) {
        if (this.record.media_type.raw_value !== "instagram") {
            return super.openComments(ev);
        }
        ev.stopPropagation();
        const postId = this.record.id.raw_value;
        rpc('/social_instagram/get_comments', {
            stream_post_id: postId,
            comments_count: this.commentsCount,
        }).then((result) => {
            this.dialog.add(StreamPostCommentsInstagram, {
                title: _t('Instagram Comments'),
                commentCount: this.commentCount,
                originalPost: this.props.record,
                accountId: this.record.account_id.raw_value,
                postId: postId,
                comments: result.comments,
                nextRecordsToken: result.nextRecordsToken,
                commentsDisabled: this.record.instagram_comments_disabled.raw_value,
            });
        });
    },
});
