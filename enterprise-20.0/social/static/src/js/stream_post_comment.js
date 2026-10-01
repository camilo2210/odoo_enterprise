import { _t } from "@web/core/l10n/translation";
import { SocialPostFormatterMixin } from './social_post_formatter_mixin';
import { StreamPostCommentsReply } from './stream_post_comments_reply';

import { rpc } from "@web/core/network/rpc";
import { ConfirmationDialog } from '@web/core/confirmation_dialog/confirmation_dialog';
import { useService } from '@web/core/utils/hooks';
import { Component, proxy, t, useOnChange, useProps } from "@odoo/owl";

export class StreamPostComment extends SocialPostFormatterMixin(Component) {
    static template = "social.StreamPostComment";

    props = useProps({
        _onReplyComment: t.any().optional(),
        account: t.any().optional(),
        comment: t.any(),
        isSubComment: t.any().optional(),
        mediaSpecificProps: t.any(),
        onDeleteComment: t.any(),
        originalPost: t.any(),
        preventAddComment: t.any(),
        toggleUserLikes: t.any(),
    });

    setup() {
        super.setup();
        this.dialog = useService('dialog');
        this.action = proxy({
            showSubComment: false,
            showReplyComment: false,
        });
        this.state = proxy({
            comment: this.props.comment,
            isEditMode: false,
        });
        useOnChange(
            () => [this.props.comment],
            (comment) => {
                this.state.comment = comment;
            },
            { initialRun: false }
        );
    }

    //----------
    // Handlers
    //----------

    async _onLoadReplies() {
        this.action.showSubComment = true;
    }

    async _onReplyComment() {
        this.action.showReplyComment = true;
    }

    _toggleEditMode() {
        this.state.isEditMode = !this.state.isEditMode;
    }

    _onEditComment(newComment) {
        this.state.comment = newComment;
    }

    _deleteComment() {
        this.dialog.add(ConfirmationDialog, {
            title: _t('Delete Comment'),
            body: _t('Do you really want to delete this %(comment)s?\nIt will also be deleted from %(platform)s.', {
                comment: this.commentName,
                platform: this.originalPost.media_type.value
            }),
            confirmLabel: _t("Delete"),
            confirm: () => {
                this._confirmDeleteComment();
            },
            cancel: () => {},
        });
    }

    //---------
    // Private
    //---------

    async _confirmDeleteComment() {
        await rpc(this.deleteCommentEndpoint, {
            stream_post_id: this.originalPost.id.raw_value,
            comment_id: this.comment.id,
        });

        this.props.onDeleteComment();
    }

    //-------
    // Utils
    //-------

    formatComment(commentMessage) {
        return this._formatPost(commentMessage);
    }

    //----------
    // Getters
    //----------

    get comment() {
        return this.state.comment;
    }

    get account() {
        return this.props.account;
    }

    get originalPost() {
        return this.props.originalPost;
    }

    get deleteCommentEndpoint() {
        return null;
    }

    get authorPictureSrc() {
        return '';
    }

    get currentAuthorPictureSrc() {
        return '';
    }

    get commentName() {
        return _t('comment');
    }

    get link() {
        return '';
    }

    get isDeletable() {
        return this.isAuthor;
    }

    get isEditable() {
        return this.isAuthor;
    }

    isManageable() {
        return this.isDeletable || this.isEditable;
    }

    get isAuthor() {
        return false;
    }

    get isLikable() {
        return true;
    }

    get likesIcon() {
        return 'thumb_up';
    }

    get likesClass() {
        return 'oi-filled';
    }

    get commentComponent() {
        return this.constructor;
    }

    get commentReplyComponent() {
        return StreamPostCommentsReply;
    }

    /**
     * @returns {DateTime} luxon DateTime representation of the created time
     */
    get commentCreatedTime() {
        return luxon.DateTime.fromISO(this.comment.created_time);
    }
}
