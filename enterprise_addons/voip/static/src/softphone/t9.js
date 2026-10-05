import { markup } from "@odoo/owl";

import { normalize } from "@web/core/l10n/utils";
import { htmlJoin } from "@web/core/utils/html";

export const T9_MAPPING = Object.freeze({
    2: "ABC",
    3: "DEF",
    4: "GHI",
    5: "JKL",
    6: "MNO",
    7: "PQRS",
    8: "TUV",
    9: "WXYZ",
});

/** @param {string} searchTerms */
export function isT9Code(searchTerms) {
    return Boolean(searchTerms) && [...searchTerms].every((letter) => letter in T9_MAPPING);
}

/**
 * @param {string|false} t9Name
 * @param {string} t9
 */
export function matchT9Name(t9Name, t9) {
    if (!t9Name) {
        return false;
    }
    return t9Name
        .trim()
        .split(" ")
        .some((t9NamePart) => t9NamePart.startsWith(t9));
}

export function highlightT9Name(name, t9Name, t9) {
    if (!t9Name) {
        return "";
    }
    const t9NameParts = t9Name.trim().split(" ");
    for (let i = 0; i < t9NameParts.length; ++i) {
        if (!t9NameParts[i].startsWith(t9)) {
            continue;
        }
        const nameParts = name.split(" ");
        const match = highlightT9Match(nameParts[i], t9);
        if (!match) {
            console.warn(`Unexpected mismatch between name and t9_name: "${name}" and "${t9Name}"`);
            return "";
        }
        return htmlJoin([...nameParts.slice(0, i), match, ...nameParts.slice(i + 1)], " ");
    }
    return "";
}

export function highlightT9Match(name, t9) {
    t9 = [...t9].reverse();
    const nameAsArr = [...name];
    let matchEnd = 0;
    for (matchEnd = 0; matchEnd < nameAsArr.length; ++matchEnd) {
        if (t9.length < 1) {
            break;
        }
        const normalized = normalize(nameAsArr[matchEnd]).toUpperCase();
        // Extra loop, in case normalizing generates more letters.
        for (const char of normalized) {
            if (t9.length === 0) {
                return "";
            }
            const possibleLetters = T9_MAPPING[t9.pop()];
            if (!possibleLetters.includes(char)) {
                return "";
            }
        }
    }
    if (t9.length !== 0) {
        return "";
    }
    return htmlJoin([
        markup`<span class="o-voip-highlighted-letter fw-bolder">`,
        ...nameAsArr.slice(0, matchEnd),
        markup`</span>`,
        ...nameAsArr.slice(matchEnd),
    ]);
}
