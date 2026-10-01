import { Component, onWillStart, proxy } from "@odoo/owl";
import { Call } from "@voip/core/common/call_model";
import { NoPhoneNumberCard } from "@voip/core/web/no_phone_number_card";
import { AddressBook } from "@voip/softphone/address_book";
import { VOIP_PAGE_SIZE } from "@voip/softphone/softphone_model";
import { tabComponents } from "@voip/softphone/tab";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * List of your most recent calls.
 */
export class History extends Component {
    static components = { ...tabComponents, AddressBook, NoPhoneNumberCard };
    static template = "voip.History";

    setup() {
        this.action = useService("action");
        this.store = useService("mail.store");
        this.voip = useService("voip");
        this.userAgent = this.voip.userAgent;
        this.ui = useService("ui");
        this.softphone = this.voip.softphone;
        this.state = proxy(this.voip.softphone.history);
        this.hasMoreCalls = true;
        this.isFetchingCalls = false;
        onWillStart(() => this.fetchRecentCalls());
    }

    get callsByDate() {
        const calls = [...this.filteredCalls];
        calls.sort((a, b) => (b.start_date || b.create_date) - (a.start_date || a.create_date));
        const today = this.store.startOfToday;
        const yesterday = today.minus({ days: 1 });
        return Map.groupBy(calls, (call) => {
            const date = call.start_date || call.create_date;
            if (today.hasSame(date, "day")) {
                return _t("Today");
            }
            if (yesterday.hasSame(date, "day")) {
                return _t("Yesterday");
            }
            return date.toLocaleString(luxon.DateTime.DATE_MED);
        });
    }

    get clearSelectedContactTitle() {
        if (this.state.previousTab) {
            return _t("Back");
        }
        return _t("Show all recent calls");
    }

    /** Get the local list of calls. Search terms are handled by the contacts view. */
    get filteredCalls() {
        const calls = [...this.voip.calls.values()];
        if (!this.state.selectedContact) {
            return calls;
        }
        return calls.filter((call) => call.partner_id?.eq(this.state.selectedContact));
    }

    get isSearchingContacts() {
        return !this.state.selectedContact && Boolean(this.state.searchInputValue);
    }

    /**
     * Identifies the history list context: the selected contact changes which
     * calls are listed, and the search value changes whether the regular
     * history tab or the contact search is displayed.
     *
     * @returns {string}
     */
    get listContextKey() {
        return `${this.state.selectedContact?.id || ""}:${this.state.searchInputValue}`;
    }

    get noEntriesMessage() {
        if (this.state.selectedContact) {
            return _t("No recent calls with this contact");
        }
        return _t("Your call history is empty! Make a call now and have it listed here 💡");
    }

    get selectedContactHistoryTitle() {
        return _t("Calls with %(contact)s", {
            contact: this.state.selectedContact.voipName,
        });
    }

    /** @returns {boolean} */
    get showsNoNumberCard() {
        return !this.state.selectedContact && this.voip.showsNoNumberHeader;
    }

    getStatusColor(call) {
        switch (call.state) {
            case "rejected":
            case "missed":
                return "text-danger";
            case "calling":
            case "ongoing":
                return this.isInProgress(call) ? "" : "text-danger";
            case "aborted":
            case "terminated":
            default:
                return "";
        }
    }

    /** @returns {string} */
    getStatusText(call) {
        const isInProgress = this.isInProgress(call);
        const { direction, durationString: duration, state } = call;
        if (state === "terminated") {
            return direction === "incoming"
                ? _t("Incoming call (%(duration)s)", { duration })
                : _t("Outgoing call (%(duration)s)", { duration });
        }
        return Call.getStatus({ isInProgress, state });
    }

    /**
     * @param {import("models").Call} call
     * @returns {Object[]}
     */
    getSubtitleExtraIcons(call) {
        if (call.has_recording) {
            return [{ name: "graphic_eq", title: _t("Recording") }];
        }
        return [];
    }

    getSubtitleIcon(call) {
        return call.direction === "incoming" ? "south_west" : "north_east";
    }

    getSubtitleIconClass(call) {
        const classes = ["oi-fw oi-sm"];
        switch (call.state) {
            case "terminated":
                classes.push("text-success");
                break;
            case "rejected":
            case "missed":
                classes.push("text-danger");
                break;
            case "calling":
            case "ongoing":
                classes.push(this.isInProgress(call) ? "text-muted" : "text-danger");
                break;
            case "aborted":
            default:
                classes.push("text-muted");
                break;
        }
        return classes.join(" ");
    }

    isInProgress(call) {
        return this.userAgent.isInProgress(call);
    }

    async fetchRecentCalls({ offset = 0, partnerId = this.state.selectedContact?.id } = {}) {
        if (this.isFetchingCalls || (offset && !this.hasMoreCalls)) {
            return;
        }
        this.isFetchingCalls = true;
        try {
            const callIds = await this.voip.fetchRecentCalls({
                limit: VOIP_PAGE_SIZE,
                offset,
                partnerId,
            });
            this.hasMoreCalls = callIds.length === VOIP_PAGE_SIZE;
        } finally {
            this.isFetchingCalls = false;
        }
    }

    clearSearch() {
        this.state.previousTab = null;
        this.state.selectedContact = null;
        this.state.searchInputValue = "";
    }

    clearSelectedContact() {
        const previousTab = this.state.previousTab;
        this.clearSearch();
        if (previousTab) {
            this.softphone.activeTab = previousTab;
        } else {
            this.fetchRecentCalls();
        }
    }

    onInputSearch(ev) {
        this.state.previousTab = null;
        this.state.selectedContact = null;
    }

    onClickCall(call) {
        this.userAgent.makeCall({ partner: call.partner_id, phone_number: call.phone_number });
    }

    onClickCallHistory(call) {
        this.onClickContactHistory(call.partner_id);
    }

    onClickContactHistory(contact) {
        this.softphone.openContactHistory(contact);
        this.fetchRecentCalls({ partnerId: contact.id });
    }

    openFullHistory() {
        const views = [
            [false, "list"],
            [false, "graph"],
            [false, "pivot"],
            [false, "form"],
        ];
        if (this.ui.isSmall) {
            views.unshift([false, "kanban"]);
        }
        const action = {
            type: "ir.actions.act_window",
            name: _t("Recent Calls"),
            res_model: "voip.call",
            target: this.ui.isSmall ? "new" : "current",
            views,
            context: {
                search_default_my_calls: 1,
            },
        };
        if (this.state.selectedContact) {
            action.context.search_default_partner_id = this.state.selectedContact.id;
        }
        this.action.doAction(action);
        this.softphone.hide();
    }
}
