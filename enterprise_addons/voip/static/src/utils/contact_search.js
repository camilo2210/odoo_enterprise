import { isT9Code, matchT9Name } from "@voip/softphone/t9";
import { isSubstring, matchPhoneNumber } from "@voip/utils/utils";

/** @typedef {import("models").ResPartner} ResPartner */

/** @param {string} lang */
export function makeContactComparator(lang) {
    const compareNames = new Intl.Collator(lang, {
        collation: "phonebk", // In German, "Müller" should be equivalent to "Mueller".
        numeric: true, // Sort numbers by value, i.e. "Guest 9" should come before "Guest 100".
    }).compare;
    return (a, b) => {
        if (!a.voipName && b.voipName) {
            return 1;
        }
        if (a.voipName && !b.voipName) {
            return -1;
        }
        return compareNames(a.voipName, b.voipName);
    };
}

/**
 * @param {ResPartner[]} contacts
 * @param {string} searchTerms
 * @returns {ResPartner[]}
 */
export function getMatchingContacts(contacts, searchTerms) {
    const isT9Search = isT9Code(searchTerms);
    return searchTerms
        ? contacts.filter(
              (contact) =>
                  isSubstring(contact.complete_name, searchTerms) ||
                  matchPhoneNumber(contact.phone, searchTerms) ||
                  matchPhoneNumber(contact.phone_formatted || "", searchTerms) ||
                  isSubstring(contact.email, searchTerms) ||
                  (isT9Search && matchT9Name(contact.t9_name, searchTerms))
          )
        : [...contacts];
}

/**
 * @param {ResPartner[]} contacts
 * @param {string} searchTerms
 * @param {(a: ResPartner, b: ResPartner) => number} compareContacts
 * @returns {ResPartner[]}
 */
export function getSortedMatchingContacts(contacts, searchTerms, compareContacts) {
    return getMatchingContacts(contacts, searchTerms).sort(compareContacts);
}

/**
 * @param {ResPartner[]} contacts
 * @param {number[]} contactIds
 * @returns {ResPartner[]}
 */
export function prioritizeContactsByIds(contacts, contactIds) {
    const contactsById = new Map(contacts.map((contact) => [contact.id, contact]));
    const contactIdSet = new Set(contactIds);
    return [
        ...contactIds.map((contactId) => contactsById.get(contactId)).filter(Boolean),
        ...contacts.filter((contact) => !contactIdSet.has(contact.id)),
    ];
}
