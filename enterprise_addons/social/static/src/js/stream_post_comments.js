import { useSubEnv } from "@web/owl2/utils";
import { MediaCarouselDialog } from "./media_carousel_dialog";
import { StreamPostCommentList } from "./stream_post_comment_list";
import { StreamPostCommentsReply } from "./stream_post_comments_reply";
import { SocialPostFormatterMixin } from "./social_post_formatter_mixin";

import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { getFormattedRecord } from "@web/views/kanban/kanban_record";
import { Component, proxy, t, useProps } from "@odoo/owl";

export class StreamPostComments extends SocialPostFormatterMixin(Component) {
    static template = "social.StreamPostComments";
    static components = { Dialog };

    props = useProps({
        accountId: t.any(),
        comments: t.any(),
        commentsCount: t.any().optional(),
        error: t.any().optional(),
        nextRecordsToken: t.any().optional(),
        onPostDeleted: t.any().optional(),
        onPostUpdate: t.any().optional(),
        originalPost: t.any(),
        postId: t.any(),
        title: t.any(),
    });

    setup() {
        super.setup();
        this.orm = useService('orm');
        this.dialog = useService('dialog');
        this.comments = proxy(this.props.comments);
        this.postId = this.props.postId;

        this.state = proxy({
            displayModal: true,
            showLoadMoreComments: false,
            isEditMode: false,
            // because this component is inside a modal, it's not possible to
            // change his props from his parent with a event handler without
            // re-creating the modal, so we duplicate the message into the state
            message: this._formatStreamPostForEdition(this.originalPost.message.raw_value),
        });

        this.mediaSpecificProps = {};

        useSubEnv({
            closeCommentsModal: this.closeCommentsModal.bind(this)
        });
    }

    //----------
    // Handlers
    //----------

    onClickMoreMedias(index, medias) {
        this.dialog.add(MediaCarouselDialog, {
            title: _t("Post Medias"),
            activeIndex: index,
            medias: medias,
            mediaType: this.props.originalPost.data.media_type,
        });
    }

    closeCommentsModal() {
        this.state.displayModal = false;
    }

    loadMoreComments() {
        // to be defined by social-media sub-implementations
    }

    onAddComment(newComment) {
        this.comments.unshift(newComment);
    }

    onDeletePost() {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Delete Post"),
            body: _t("Do you really want to delete this Post? It will also be deleted from %(platform)s.", {
                platform: this.originalPost.media_type.value
            }),
            confirm: async () => {
                await rpc(`/social_${this.props.originalPost.data.media_type}/delete_post`, {
                    stream_post_id: this.props.originalPost.resId,
                });
                if (this.props.onPostDeleted) {
                    this.props.onPostDeleted();
                }
            },
            confirmLabel: _t("Delete Post"),
            cancel: () => {},
        });
    }

    async onEditPost(event) {
        const textarea = event.currentTarget;
        if (
            event.key !== "Enter" ||
            event.ctrlKey ||
            event.shiftKey ||
            textarea.value.trim() === ""
        ) {
            return;
        }

        this.state.isEditMode = false;
        this.state.message = textarea.value;

        await rpc(`/social_${this.props.originalPost.data.media_type}/edit_post`, {
            stream_post_id: this.props.originalPost.resId,
            new_message: textarea.value,
        });

        this.props?.onPostUpdate(textarea.value);
    }

    preventAddComment(textarea, replyToCommentId) {
        return false;
    }

    _formatCommentStreamPost(message) {
        return this._formatPost(message);
    }

    _formatStreamPostForEdition(message) {
        return message;
    }

    get bodyClass() {
        return 'o_social_comments_modal o_social_comments_modal_' + this.originalPost.media_type.raw_value + ' pt-0 px-0 bg-100';
    }

    get originalPost() {
        return getFormattedRecord(this.props.originalPost);
    }

    get JSON() {
        return JSON;
    }

    get commentListComponent() {
        return StreamPostCommentList;
    }

    get commentReplyComponent() {
        return StreamPostCommentsReply;
    }

    get isAuthor() {
        return this.originalPost.is_author && this.originalPost.is_author.raw_value;
    }

    get isDeletable() {
        return false;
    }

    get isEditable() {
        return false;
    }

    get commentsDisabled() {
        return false;
    }

    get authorTitle() {
        return this.props.originalPost.data.author_name || _t("Unknown");
    }
}
