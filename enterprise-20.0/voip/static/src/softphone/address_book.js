import { Component, onMounted, useProps, proxy, t, useEffect } from "@odoo/owl";

import {
    getSortedMatchingContacts,
    makeContactComparator,
    prioritizeContactsByIds,
} from "@voip/utils/contact_search";
import { tabComponents } from "@voip/softphone/tab";
import { highlightT9Name, isT9Code } from "@voip/softphone/t9";
import { highlightMatch, highlightPhone } from "@voip/utils/highlight";

import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { htmlJoin } from "@web/core/utils/html";
import { useDebounced } from "@web/core/utils/timing";

export const PRIORITIZED_CONTACT_LIMIT = 3;

/** @typedef {import("models").ResPartner} ResPartner */

/**
 * List of contacts, i.e. people you can call.
 */
export class AddressBook extends Component {
    static components = tabComponents;
    props = useProps({
        contactsFilter: t.function().optional(() => (contact) => true),
        onContactCalled: t.function().optional(),
        onClickHistory: t.function().optional(),
        onClickBack: t.function().optional(),
        onInputSearch: t.function().optional(),
        searchInternalUsersFirst: t.boolean().optional(false),
        searchPlaceholder: t.string().optional(),
        showPrioritizedContacts: t.boolean().optional(false),
        slots: t.object().optional(),
        state: t.object().optional(), // See this.state
    });
    static template = "voip.AddressBook";

    setup() {
        this.action = useService("action");
        this.voip = useService("voip");
        this.userAgent = this.voip.userAgent;
        this.ui = useService("ui");
        // Either use the dedicated state or the one given by the top component
        // (typically, the History component might just contain an unique
        // address book once a search is performed).
        this.state = proxy(this.props.state || this.voip.softphone.addressBook);
        this.prioritizedContactIdsBySearchTerms = this.state.prioritizedContactIdsBySearchTerms ??=
            new Map();
        this.prioritizedContacts = proxy({ contactIds: this.cachedPrioritizedContactIds });
        this.compareContacts = makeContactComparator(user.lang);
        this.fetchContactsDebounced = useDebounced(() => this.fetchContacts(), 300);
        this.lastSearchInputValue = this.state.searchInputValue;
        useEffect(() => {
            const searchInputValue = this.state.searchInputValue;
            if (searchInputValue === this.lastSearchInputValue) {
                return;
            }
            this.lastSearchInputValue = searchInputValue;
            this.prioritizedContacts.contactIds = this.cachedPrioritizedContactIds;
            this.fetchContactsDebounced();
        });
        onMounted(() => this.fetchContacts());
    }

    get searchTerms() {
        return this.state.searchInputValue.trim();
    }

    get shouldSearchInternalUsersFirst() {
        // Use the raw input so entering whitespace can prioritize internal users
        // without filtering contacts by a search term.
        return Boolean(this.props.searchInternalUsersFirst && this.state.searchInputValue);
    }

    get cachedPrioritizedContactIds() {
        if (!this.shouldDisplayPrioritizedContacts) {
            return [];
        }
        return this.prioritizedContactIdsBySearchTerms.get(this.searchTerms) || [];
    }

    /** @returns {ResPartner[]} */
    get sortedContacts() {
        let compareContacts = this.compareContacts;
        if (this.shouldSearchInternalUsersFirst) {
            compareContacts = (a, b) => {
                const shareComparison =
                    Number(a.partner_share !== false) - Number(b.partner_share !== false);
                return shareComparison || this.compareContacts(a, b);
            };
        }
        const contacts = getSortedMatchingContacts(
            this.voip.softphone.contacts.filter(this.props.contactsFilter),
            this.searchTerms,
            compareContacts
        );
        if (!this.shouldDisplayPrioritizedContacts) {
            return contacts;
        }
        return prioritizeContactsByIds(contacts, this.prioritizedContacts.contactIds);
    }

    get shouldDisplayPrioritizedContacts() {
        // Use the raw input so entering whitespace can prioritize recently
        // called contacts without filtering contacts by a search term.
        return Boolean(this.props.showPrioritizedContacts && this.state.searchInputValue);
    }

    async fetchContacts({ loadMore = false } = {}) {
        const searchTerms = this.searchTerms;
        const prioritizedContactsLimit = this.shouldDisplayPrioritizedContacts
            ? PRIORITIZED_CONTACT_LIMIT
            : 0;
        const prioritizedContactIds = await this.voip.fetchContacts({
            searchTerms,
            loadMore,
            internalUsersFirst: this.shouldSearchInternalUsersFirst,
            prioritizedContactsLimit,
        });
        // Ignore a response when the search changed while the RPC was in flight
        if (!loadMore && this.searchTerms === searchTerms) {
            if (prioritizedContactsLimit) {
                this.prioritizedContactIdsBySearchTerms.set(searchTerms, prioritizedContactIds);
                this.prioritizedContacts.contactIds = prioritizedContactIds;
            } else {
                this.prioritizedContacts.contactIds = [];
            }
        }
    }

    /**
     * @param {ResPartner} contact
     * @returns {{
     *   title: ReturnType<markup>|string|undefined,
     *   subtitle: { icon: string, text: ReturnType<markup>|string },
     * }}
     */
    getTitleData(contact) {
        // TabEntry provides the unhighlighted name or phone fallback when this
        // stays undefined.
        let highlightedTitle;
        if (this.searchTerms) {
            const terms = this.searchTerms;
            highlightedTitle =
                (isT9Code(terms) && highlightT9Name(contact.voipName, contact.t9_name, terms)) ||
                highlightMatch(contact.voipName, terms) ||
                (!contact.voipName &&
                    (highlightPhone(contact.phone, terms) ||
                        highlightPhone(contact.phone_formatted || "", terms))) ||
                undefined;
        }

        // A person's company and function form the default subtitle
        const highlightedParentName =
            this.searchTerms && contact.parent_name
                ? highlightMatch(contact.parent_name, this.searchTerms)
                : "";
        const parentName = highlightedParentName || contact.parent_name;
        const parts = [parentName, contact.function].filter(Boolean);
        const subtitleText = !contact.is_company && parts.length ? htmlJoin(parts, " - ") : "";
        const subtitleData = {
            icon: subtitleText ? "business" : "",
            text: subtitleText,
        };
        // Keep that subtitle when it already contains the match, or when there
        // is no search.
        if (!this.searchTerms || highlightedParentName) {
            return { title: highlightedTitle, subtitle: subtitleData };
        }
        // Named contacts show a matching phone number as their subtitle. For
        // nameless contacts, the same match is already used as the title above.
        if (contact.voipName) {
            const highlightedPhoneNumber =
                highlightPhone(contact.phone, this.searchTerms) ||
                highlightPhone(contact.phone_formatted || "", this.searchTerms);
            if (highlightedPhoneNumber) {
                subtitleData.icon = "";
                subtitleData.text = highlightedPhoneNumber;
                return { title: highlightedTitle, subtitle: subtitleData };
            }
        }
        // complete_name may contain a commercial company or address label not
        // shown above.
        if (!highlightedTitle) {
            for (const fieldValue of [contact.complete_name, contact.email]) {
                const highlightedFieldValue = highlightMatch(fieldValue || "", this.searchTerms);
                if (highlightedFieldValue) {
                    subtitleData.icon = "";
                    subtitleData.text = highlightedFieldValue;
                    break;
                }
            }
        }
        return { title: highlightedTitle, subtitle: subtitleData };
    }

    /** @param {ResPartner} contact */
    onClickCall(contact) {
        this.props.onContactCalled?.();
        this.userAgent.makeCall({ partner: contact, phone_number: contact.phone });
        this.voip.softphone.inCallView.reset();
    }

    onInputSearch(ev) {
        this.props.onInputSearch?.(ev);
    }

    openPartnerForm() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            target: this.ui.isSmall ? "new" : "current",
        });
    }
}
