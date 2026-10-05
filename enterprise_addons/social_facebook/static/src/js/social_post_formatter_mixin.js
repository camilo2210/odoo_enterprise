import { htmlToTextContentInline } from "@mail/utils/common/format";

import { htmlEscape, markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace, htmlReplaceAll } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Facebook @tag and #hashtag support.
 * Replace all occurrences of `#hashtag` and of `@tag` by a HTML link to a
 * search of the hashtag/tag on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        const mediaType = this._getMediaType();
        if (["facebook", "facebook_preview"].includes(mediaType)) {
            value = htmlReplace(value, SocialPostFormatterRegex.REGEX_HASHTAG, (_, hashtag) => {
                /**
                 * markup: value is a Markup object (either escaped inside htmlReplace or
                 * flagged safe), `hashtag` is directly coming from this value,
                 * and the regex doesn't do anything crazy to unescape it.
                 */
                hashtag = markup(hashtag);
                return markup`<a href='https://www.facebook.com/hashtag/${hashtag}' target='_blank'>#${hashtag}</a>`;
            });
        }
        const resModel = this.props?.record?.config.resModel;
        if (mediaType === "facebook" && (resModel === "social.stream.post" || this.originalPost)) {
            // Stream post view, name in the body should be extracted
            const accountId =
                this.props?.record?.data.account_id?.id || this.originalPost?.account_id.raw_value;
            if (accountId) {
                // Facebook uses a special regex for "@person" support.
                // See social.stream.post#_format_facebook_message for more information.
                // &#x27; is the escaped character for '.
                const REGEX_AT_FACEBOOK = /(?<=^|\s|<br>)@\[([0-9]*)\]\s([\w\dÀ-ÿ-&#x27;]+)/gu;
                value = htmlReplace(value, REGEX_AT_FACEBOOK, (_, id, name) => {
                    /**
                     * markup: value is a Markup object (either escaped inside htmlReplace or
                     * flagged safe), `id` and `name` are directly coming from this value, and
                     * the regex doesn't do anything crazy to unescape them.
                     */
                    id = markup(id);
                    name = markup(name);
                    // `name` is escaped, decode it before URL encode
                    const encodedName = encodeURIComponent(htmlToTextContentInline(name));
                    return markup`<a href='/social_facebook/redirect_to_profile/${id}?name=${encodedName}&account_ids=[${encodeURIComponent(
                        accountId
                    )}]' target='_blank'>${name}</a>`;
                });
            }
        } else if (
            mediaType === "facebook_preview" ||
            (mediaType === "facebook" && resModel === "social.live.post")
        ) {
            // facebook: live post / facebook_preview: social post (no name in the body, take it from `social_post_mentions`)
            const post =
                mediaType === "facebook" ? this.props.record._parentRecord : this.props.record;
            const mentions = JSON.parse(post.data.social_post_mentions || "{}")["facebook"] || {};
            value = htmlReplaceAll(
                value,
                /(?<=^|\s|<br>)@(\[[0-9]+\])/g,
                (originalValue, facebookId) => {
                    if (!mentions[facebookId]) {
                        return originalValue;
                    }
                    return markup`<a href='/social_facebook/redirect_to_profile/${htmlEscape(
                        Number(mentions[facebookId].id)
                    )}?account_ids=${JSON.stringify(
                        post.data.account_ids.resIds
                    )}&name=${htmlEscape(
                        encodeURIComponent(mentions[facebookId].name)
                    )}' target='_blank'>${htmlEscape(mentions[facebookId].name)}</a>`;
                }
            );
        }
        return value;
    },
});
