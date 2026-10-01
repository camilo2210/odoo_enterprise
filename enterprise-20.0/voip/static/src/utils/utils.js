import { normalize } from "@web/core/l10n/utils";
import { cleanPhoneNumber } from "@web/core/phone/phone_call";
import { escapeRegExp } from "@web/core/utils/strings";

// TODO remove in master
export { cleanPhoneNumber };

/**
 * Compares two phone numbers by digits only, ignoring formatting differences
 * (e.g. `+`, spaces, dashes). Useful when comparing numbers from different
 * sources (SIP URI user vs stored number).
 *
 * @param {string} a
 * @param {string} b
 * @returns {boolean}
 */
export function isSamePhoneNumber(a, b) {
    if (!a || !b) {
        return false;
    }
    const normalize = (n) => {
        n = n.replace(/[^0-9+]/g, "");
        if (n.startsWith("00")) {
            n = "+" + n.slice(2);
        }
        if (n.startsWith("0")) {
            n = n.slice(1);
        }
        return n;
    };
    const aN = normalize(a);
    const bN = normalize(b);
    if (aN.startsWith("+") === bN.startsWith("+")) {
        // Same type (both international or both local) —> compare directly.
        return aN === bN;
    }
    // One is international, the other local —> match by suffix.
    return aN.endsWith(bN) || bN.endsWith(aN);
}

/**
 * A multiset of phone numbers where membership is tested using
 * {@link isSamePhoneNumber} rather than strict equality.
 * Unlike a regular Set, the same number can be added multiple times and
 * each {@link delete} call removes only one occurrence.
 */
export class PhoneNumberMultiSet {
    /** @type {Map<string, number>} */
    _phones = new Map();

    /**
     * @param {string} phoneNumber
     * @returns {string|undefined}
     */
    _findNumber(phoneNumber) {
        return this._phones.keys().find((number) => isSamePhoneNumber(number, phoneNumber));
    }

    /**
     * @param {string} phoneNumber
     */
    add(phoneNumber) {
        const number = this._findNumber(phoneNumber);
        if (number !== undefined) {
            this._phones.set(number, this._phones.get(number) + 1);
        } else {
            this._phones.set(phoneNumber, 1);
        }
    }

    /**
     * @param {string} phoneNumber
     * @returns {boolean}
     */
    has(phoneNumber) {
        return this._findNumber(phoneNumber) !== undefined;
    }

    /**
     * Removes one occurrence of a phone number from the multiset.
     * When multiple internationally-prefixed variants of the same local number
     * are stored (e.g. "+44123" and "+55123"), `_findNumber` returns the first
     * match found; this is acceptable because the same local number is never
     * expected to exist under two different country prefixes simultaneously.
     *
     * @param {string} phoneNumber
     * @returns {boolean}
     */
    delete(phoneNumber) {
        const number = this._findNumber(phoneNumber);
        if (number === undefined) {
            return false;
        }
        const count = this._phones.get(number) - 1;
        if (count === 0) {
            this._phones.delete(number);
        } else {
            this._phones.set(number, count);
        }
        return true;
    }

    clear() {
        this._phones.clear();
    }

    /** @returns {number} */
    get size() {
        return this._phones.values().reduce((total, count) => total + count, 0);
    }
}

const editableInputTypes = new Set([
    "date",
    "datetime-local",
    "email",
    "month",
    "number",
    "password",
    "search",
    "tel",
    "text",
    "time",
    "url",
    "week",
]);

/**
 * Determines whether the currently focused element is editable. This is useful
 * for preventing auto-focus mechanisms when the user is already typing
 * elsewhere.
 *
 * @returns {boolean}
 */
export function isCurrentFocusEditable() {
    const el = document.activeElement;
    if (!el) {
        return false;
    }
    if (el.isContentEditable) {
        return true;
    }
    const tag = el.tagName.toLowerCase();
    if (tag === "textarea") {
        return true;
    }
    if (tag === "input") {
        const inputType = el.getAttribute("type")?.toLowerCase() || "text";
        return editableInputTypes.has(inputType);
    }
    return false;
}

export function isSubstring(targetString, substring) {
    if (!targetString) {
        return false;
    }
    return normalize(targetString).includes(normalize(substring));
}

const PHONE_SEARCH_MIN_LENGTH = 3; // See _phone_search_min_length

/**
 * Matches a target number against a search term and returns a three-part result
 * for highlighting.
 *
 * @param {string} targetNumber - The full phone number to search within.
 * @param {string} searchTerms - The user's original search term.
 * @returns {{before: string, match: string, after: string} | null}
 * An object with the following properties if a match is found, otherwise null:
 * - `before`: The substring of `targetNumber` that comes *before* the match.
 * - `match`: The actual substring of `targetNumber` that *matched* the regex.
 * - `after`: The substring of `targetNumber` that comes *after* the match.
 */
export function matchPhoneNumber(targetNumber, searchTerms) {
    if (/[a-zA-Z]/.test(searchTerms)) {
        return null;
    }
    const r = String.raw;
    const hasPlusPrefix = searchTerms.trim().startsWith("+");
    const sanitizedSearchTerms = searchTerms.replace(/[^0-9*#;,]/g, "");
    if (searchTerms.trim().length < PHONE_SEARCH_MIN_LENGTH) {
        return null;
    }
    let regexString = Array.from(sanitizedSearchTerms, escapeRegExp).join(r`\D*`);
    if (!regexString && !hasPlusPrefix) {
        return null;
    }
    if (hasPlusPrefix) {
        regexString = r`\+\D*${regexString}`;
    }
    const regex = new RegExp(`(^.*?)(${regexString})(.*?$)`, "i");
    const [, before, match, after] = targetNumber.match(regex) ?? [];
    if (match) {
        return { before, match, after };
    }
    return null;
}
