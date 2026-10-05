import { _t } from "@web/core/l10n/translation";
import { StreamPostKanbanRecord } from "@social/js/stream_post_kanban_record";
import { StreamPostCommentsTwitter } from "./stream_post_comments";
import { StreamPostTwitterQuote } from "./stream_post_twitter_quote";

import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { markup, useListener } from "@odoo/owl";

patch(StreamPostKanbanRecord.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");

        const likesEl = () => this.rootRef()?.querySelector(".o_social_twitter_likes");
        const retweetEl = () => this.rootRef()?.querySelector(".o_social_twitter_retweet");
        const quoteEl = () => this.rootRef()?.querySelector(".o_social_twitter_quote");
        useListener(likesEl, "click", this._onTwitterTweetLike.bind(this));
        useListener(retweetEl, "click", this._onTwitterRetweet.bind(this));
        useListener(quoteEl, "click", this._onTwitterQuote.bind(this));
    },

    openComments(ev) {
        if (this.record.media_type.raw_value !== "twitter") {
            return super.openComments(ev);
        }
        ev.stopPropagation();
        const postId = this.record.id.raw_value;

        const modalInfo = {
            title: _t("Twitter Comments"),
            accountId: this.record.account_id.raw_value,
            originalPost: this.props.record,
            onTwitterTweetLike: this._onTwitterTweetLike.bind(this),
            postId: postId,
            streamId: this.record.stream_id.raw_value,
        };

        rpc("/social_twitter/get_comments", { stream_post_id: postId })
            .then((result) => {
                this.dialog.add(StreamPostCommentsTwitter, {
                    ...modalInfo,
                    commentsCount: this.commentsCount,
                    allComments: result.comments,
                    comments: result.comments.slice(0, this.commentsCount),
                    isReplyLimited: result.is_reply_limited,
                });
            })
            .catch((error) => {
                const errorBody = /\bx\.com\b/.test(error.data.message)
                    ? markup`<a href="${this.record.post_link.value}" target="_blank" class="text-info text-opacity-100">${error.data.message}</a>`
                    : error.data.message;
                this.dialog.add(StreamPostCommentsTwitter, {
                    ...modalInfo,
                    commentsCount: 0,
                    allComments: [],
                    comments: [],
                    isReplyLimited: true,
                    error: errorBody,
                });
            });
    },

    async _onTwitterTweetLike() {
        const userLikes = this.record.twitter_user_likes.raw_value;
        await rpc(
            `/social_twitter/${encodeURIComponent(this.record.stream_id.raw_value)}/like_tweet`,
            {
                tweet_id: this.record.twitter_tweet_id.raw_value,
                like: !userLikes,
            }
        );
        for (const record of this.props.record.model.root.records) {
            if (record.data.twitter_tweet_id === this.props.record.data.twitter_tweet_id) {
                await record.load();
            }
        }
    },

    _onTwitterRetweet(ev) {
        const action = this.record.twitter_can_retweet.raw_value ? "retweet" : "unretweet";
        rpc(`/social_twitter/${encodeURIComponent(this.record.stream_id.raw_value)}/${action}`, {
            tweet_id: this.record.twitter_tweet_id.raw_value,
            stream_id: this.record.stream_id.raw_value,
        }).then((result) => {
            result = JSON.parse(result);
            if (result === true) {
                const retweetCount = this.record.twitter_can_retweet.raw_value
                    ? this.record.twitter_retweet_count.raw_value + 1
                    : this.record.twitter_retweet_count.raw_value - 1;
                this.props.record.update({
                    twitter_can_retweet: !this.record.twitter_can_retweet.raw_value,
                    twitter_retweet_count: retweetCount,
                });
            } else if (result.error) {
                this.notification.add(result.error, {
                    title: _t("Error"),
                    type: "danger",
                });
            }
        });
    },

    _onTwitterQuote() {
        this.dialog.add(StreamPostTwitterQuote, {
            title: _t("Quote a Tweet"),
            mediaSpecificProps: {
                accountId: this.record.account_id.raw_value,
                accountName: this.record.author_name.value,
            },
            originalPost: this.props.record,
            onTwitterTweetLike: this._onTwitterTweetLike.bind(this),
            refreshStats: () => this.env.refreshStats(),
        });
    },
});
