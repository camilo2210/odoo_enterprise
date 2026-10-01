import { StreamPostComment } from './stream_post_comment';
import { Component, t, useProps } from "@odoo/owl";

export class StreamPostCommentList extends Component {
    static template = "social.StreamPostCommentsWrapper";

    props = useProps({
        comments: t.array(),
        account: t.object().optional(),
        error: t.string().optional(),
        mediaSpecificProps: t.object(),
        originalPost: t.object(),
        preventAddComment: t.function(),
    });

    /**
     * To override for each specific social StreamPostCommentList class.
     * 
     * @param comment
     */
    toggleUserLikes(comment) {}


    _updateLikes(comment) {
        if (comment.user_likes) {
            if (comment.likes.summary.total_count > 0)
                comment.likes.summary.total_count--;
        } else {
            comment.likes.summary.total_count++;
        }
        comment.user_likes = !comment.user_likes;
    }

    get comments() {
        return this.props.comments;
    }

    get account() {
        return this.props.account;
    }

    get originalPost() {
        return this.props.originalPost;
    }

    get commentComponent() {
        return StreamPostComment;
    }

}
