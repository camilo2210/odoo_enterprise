import { htmlEscape, markup } from "@odoo/owl";

import {
    SocialPostFormatterMixinBase,
    SocialPostFormatterRegex,
} from "@social/js/social_post_formatter_mixin";

import { htmlReplace, htmlReplaceAll } from "@web/core/utils/html";
import { patch } from "@web/core/utils/patch";

export const LINKEDIN_HASHTAG_REGEX = /(?<=(?:^|\s|<br>)){hashtag\|#\|([a-zA-Z\d\-_]+)}(?=(?:$|\s|<br>))/g;
export const LINKEDIN_AT_REGEX =
    /(?<=(?:^|\s|<br>))@\[((?:\w+)(?:(?:\s|-)\w+)*)\]\(urn:li:(person|organization):\w+?\)(?=(?:$|\s|<br>))/g;
export const INTERNAL_LINKEDIN_AT_REGEX = /(?<=(?:^|\s|<br>))@([a-zA-Z-_]+)/g;

/*
 * Add LinkedIn #hashtag and mentions support.
 * Replace all occurrences of `#hashtag` by a HTML link to a search of the hashtag
 * on the media website
 * Replace all occurrences of `@vanity_name` by a link to the mentioned page on LinkedIn.
 */
patch(SocialPostFormatterMixinBase, {
    _formatPost(value) {
        value = super._formatPost(...arguments);
        if (this._getMediaType() === "linkedin") {
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
                    return markup`<a href='https://www.linkedin.com/feed/hashtag/?keywords=${hashtag}' target='_blank'>#${hashtag}</a>`;
                }
            );
            value = htmlReplace(value, LINKEDIN_HASHTAG_REGEX, (_, name) => {
                /**
                 * markup: value is a Markup object (either escaped inside htmlReplace or flagged
                 * safe), `name` is directly coming from this value, and the regex doesn't do
                 * anything crazy to unescape it.
                 */
                name = markup(name);
                return markup`<a href='https://www.linkedin.com/feed/hashtag/?keywords=${name}' target='_blank'>#${name}</a>`;
            });
            value = htmlReplaceAll(value, LINKEDIN_AT_REGEX, (_, name) => {
                /**
                 * markup: value is a Markup object (either escaped inside htmlReplace or flagged
                 * safe), `name` is directly coming from this value, and the regex doesn't do
                 * anything crazy to unescape it.
                 */
                name = markup(name);
                return markup`<a href="https://www.linkedin.com/search/results/all/?keywords=${name}">${name}</a>`;
            });
        } else if (this._getMediaType() === "linkedin_preview") {
            const mentions =
                JSON.parse(this.props.record.data.social_post_mentions || "{}")["linkedin"] || {};
            value = htmlReplaceAll(value, INTERNAL_LINKEDIN_AT_REGEX, (mention, name) => {
                const mentionVals = mentions[name];
                if (!mentionVals || !mentionVals.vanity_name) {
                    return mention;
                }
                const isOrganization = mentionVals.member.startsWith("urn:li:organization:");
                return markup`
                    <a href='https://www.linkedin.com/${isOrganization ? "company" : "in"}/
                    ${htmlEscape(mentionVals.vanity_name)}' target='_blank'>${htmlEscape(
                    mentionVals.full_name
                )}</a>`;
            });
        }
        return value;
    },
});
