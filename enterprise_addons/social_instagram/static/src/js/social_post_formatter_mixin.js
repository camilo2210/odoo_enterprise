import { htmlEscape, markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

/*
 * Add Instagram #hashtag and @mention support.
 * Replace all occurrences of `#hashtag` and `@mention` by a HTML link to a
 * search of the hashtag/mention on the media website
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        if (this._getMediaType() === "instagram") {
            value = htmlReplace(
                value,
                SocialPostFormatterRegex.REGEX_HASHTAG,
                (_, hashtag) => {
                    /**
                     * markup: value is a Markup object (either escaped inside htmlReplace or
                     * flagged safe), `hashtag` is directly coming from this value,
                     * and the regex doesn't do anything crazy to unescape it.
                     */
                    hashtag = markup(hashtag);
                    return markup`<a href='https://www.instagram.com/explore/tags/${hashtag}' target='_blank'>#${hashtag}</a>`;
                }
            );
            value = htmlReplace(value, SocialPostFormatterRegex.REGEX_AT, (_, name) => {
                /**
                 * markup: value is a Markup object (either escaped inside htmlReplace or flagged
                 * safe), `name` is directly coming from this value, and the regex doesn't do
                 * anything crazy to unescape it.
                 */
                name = markup(name);
                return markup`<a href='https://www.instagram.com/${name}' target='_blank'>@${name}</a>`;
            });
        } else if (this._getMediaType() === "instagram_preview") {
            const mentions =
                JSON.parse(this.props.record.data.social_post_mentions || "{}")["instagram"] || {};
            value = value.replaceAll(SocialPostFormatterRegex.REGEX_AT, (mention, name) => {
                if (!mentions[name]) {
                    return mention;
                }
                return markup`<a href='https://www.instagram.com/${htmlEscape(
                    name
                )}' target='_blank'>${mention}</a>`;
            });
        }
        return value;
    },
});
