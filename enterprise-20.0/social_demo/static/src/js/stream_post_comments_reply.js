import { StreamPostCommentsReplyFacebook } from "@social_facebook/js/stream_post_comments_reply";
import { StreamPostCommentsReplyInstagram } from "@social_instagram/js/stream_post_comments_reply";
import { StreamPostCommentsReplyLinkedin } from "@social_linkedin/js/stream_post_comments_reply";
import { StreamPostCommentsReplyTwitter } from "@social_twitter/js/stream_post_comments_reply";
import { StreamPostCommentsReplyYoutube } from "@social_youtube/js/stream_post_comments_reply";
import { patch } from "@web/core/utils/patch";

const toPatch = {
    get authorPictureSrc() {
        // Use the Twitter profile image that we build for all posts
        return this.props.originalPost.twitter_profile_image_url.raw_value;
    },
};

patch(StreamPostCommentsReplyFacebook.prototype, toPatch);
patch(StreamPostCommentsReplyInstagram.prototype, toPatch);
patch(StreamPostCommentsReplyLinkedin.prototype, toPatch);
patch(StreamPostCommentsReplyTwitter.prototype, toPatch);
patch(StreamPostCommentsReplyYoutube.prototype, toPatch);
