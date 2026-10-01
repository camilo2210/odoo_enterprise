import { StreamPostCommentsReply } from '@social/js/stream_post_comments_reply';

export class StreamPostCommentsReplyTwitter extends StreamPostCommentsReply {
    setup() {
        super.setup();
        this.state.disabled = !this.props.originalPost.twitter_can_reply.raw_value;
    }

    get authorPictureSrc() {
        return `/web/image/social.account/${encodeURIComponent(this.props.mediaSpecificProps.accountId)}/image/48x48`;
    }

    get addCommentEndpoint() {
        return `/social_twitter/${encodeURIComponent(this.originalPost.stream_id.raw_value)}/comment`;
    }

}
