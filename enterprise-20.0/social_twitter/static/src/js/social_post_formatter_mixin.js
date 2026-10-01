import { htmlEscape, markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace, htmlReplaceAll } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Twitter @tag and #hashtag support.
 * Replace all occurrences of `#hashtag` by a HTML link to a search of the hashtag
 * on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        if (this._getMediaType() === "twitter") {
            value = htmlReplace(
                value,
                SocialPostFormatterRegex.REGEX_HASHTAG,
                (_, hashtag) => {
                    // markup: the regex safely captures `hashtag`
                    hashtag = markup(hashtag);
                    return markup`<a href='https://twitter.com/hashtag/${encodeURIComponent(
                        hashtag
                    )}?src=hash' target='_blank'>#${hashtag}</a>`;
                }
            );
            value = htmlReplace(value, SocialPostFormatterRegex.REGEX_AT, (_, name) => {
                // markup: the regex safely captures `name`
                name = markup(name);
                return markup`<a href='https://twitter.com/${encodeURIComponent(
                    name
                )}' class="o_social_comment_mention" target='_blank'>@${name}</a>`;
            });
        } else if (this._getMediaType() === "twitter_preview") {
            const mentions =
                JSON.parse(this.props.record.data.social_post_mentions || "{}")["twitter"] || {};
            value = htmlReplaceAll(
                value,
                SocialPostFormatterRegex.REGEX_AT,
                (originalValue, userName) => {
                    if (!mentions[userName]) {
                        return originalValue;
                    }
                    return markup`<a href='https://twitter.com/${htmlEscape(
                        userName
                    )}' target='_blank'>${htmlEscape(userName)}</a>`;
                }
            );
        }
        return value;
    },
});
