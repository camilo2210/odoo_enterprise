import { _t } from "@web/core/l10n/translation";
import { CANCEL_GLOBAL_CLICK, StreamPostKanbanRecord } from '@social/js/stream_post_kanban_record';
import { StreamPostCommentsYoutube } from './stream_post_comments';

import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

patch(StreamPostKanbanRecord.prototype, {

    setup() {
        super.setup(...arguments);
    },

    openComments(ev) {
        if (this.record.media_type.raw_value !== "youtube") {
            return super.openComments(ev);
        }
        ev.stopPropagation();
        const postId = this.record.id.raw_value;
        rpc('/social_youtube/get_comments', {
            stream_post_id: postId,
            comments_count: this.commentsCount,
        }).then((result) => {
            this.dialog.add(StreamPostCommentsYoutube, {
                title: _t('YouTube Comments'),
                accountId: this.record.account_id.raw_value,
                originalPost: this.props.record,
                postId: postId,
                comments: result.comments,
                nextPageToken: result.nextPageToken,
                commentsDisabled: result.commentsDisabled,
            });
        });
    },

    onGlobalClick(ev) {
        if (ev.target.closest('.o_social_youtube_thumbnail')) {
            ev.preventDefault();
        } else if (ev.target.closest(CANCEL_GLOBAL_CLICK)) {
            return;
        }
        this._openComments(ev);
    }
});
