import { markup } from "@odoo/owl";

import { matchPhoneNumber } from "@voip/utils/utils";

import { normalizedMatch } from "@web/core/l10n/utils";
import { htmlJoin } from "@web/core/utils/html";

/**
 * @param {string} str
 * @param {string} substr
 * @returns {ReturnType<markup>|string}
 */
export function highlightMatch(str, substr) {
    const { start, end, match } = normalizedMatch(str, substr);
    return highlightMatchParts(str.slice(0, start), match, str.slice(end));
}

/**
 * @param {string} before
 * @param {string} match
 * @param {string} after
 * @returns {ReturnType<markup>|string}
 */
export function highlightMatchParts(before, match, after) {
    if (!match) {
        return "";
    }
    return htmlJoin([
        before,
        markup`<span class="o-voip-highlighted-letter fw-bolder">${match}</span>`,
        after,
    ]);
}

/**
 * @param {string} phone
 * @param {string} searchTerms
 * @returns {ReturnType<markup>|string}
 */
export function highlightPhone(phone, searchTerms) {
    const phoneMatch = matchPhoneNumber(phone, searchTerms);
    if (!phoneMatch) {
        return "";
    }
    const { before, match, after } = phoneMatch;
    return highlightMatchParts(before, match, after);
}
