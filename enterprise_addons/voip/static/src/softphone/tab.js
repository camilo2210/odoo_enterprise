import { useVisible } from "@mail/utils/common/hooks";

import { Component, onWillUnmount, useProps, signal, t, useEffect } from "@odoo/owl";

import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Generic component that defines the general structure of a softphone tab.
 */
export class Tab extends Component {
    props = useProps({
        extraClass: t.string().optional(""),
        /**
         * Function that computes the additional classes to be applied to a
         * section name. It takes the first item of the section as an argument.
         */
        getSectionStyle: t.function().optional(() => (item) => ""),
        itemsBySection: t.instanceOf(Map).optional(new Map()),
        /**
         * Items displayed without a section title, after the grouped items.
         */
        ungroupedItems: t.array().optional([]),
        /**
         * Message displayed when there are no entries in the tab.
         */
        noEntriesMessage: t.string().optional(_t("Nothing to see here 😔")),
        noSearchResultsMessage: t.string().optional(),
        onClickBack: t.function().optional(),
        /**
         * Function to be called each time the user scrolls to the end of the
         * tab. Useful to implement "load more" feature.
         */
        onTabEnd: t.function().optional(() => () => {}),
        sectionIcon: t.string().optional(""),
        /**
         * Identifies the currently displayed list context. Parent components
         * should change it when the same Tab instance starts displaying a
         * different list, so the tab can reset transient list UI state.
         */
        listContextKey: t.string().optional(""),
        state: t.object(),
    });
    static template = "voip.Tab";
    scrollContainerRef = signal(null, { type: t.ref(HTMLDivElement) });

    endOfTabRef = signal.ref();

    setup() {
        this.voip = useService("voip");

        useEffect(() => {
            this.props.listContextKey;
            this.voip.softphone.clearActiveRecord();
            this.scrollContainerRef()?.scrollTo({ top: 0 });
        });
        onWillUnmount(() => this.voip.softphone.clearActiveRecord());

        useVisible(this.endOfTabRef, (isVisible) => {
            if (isVisible) {
                this.props.onTabEnd();
            }
        });
    }

    get hasItems() {
        return this.props.itemsBySection.size > 0 || this.props.ungroupedItems.length > 0;
    }
}

import { ActionButton } from "@voip/softphone/action_button";
import { ActionList } from "@voip/softphone/action_list";
import { NoSearchResults } from "@voip/softphone/no_search_results";
import { PhoneNumber } from "@voip/softphone/phone_number";
import { SearchBar } from "@voip/softphone/search_bar";
import { TabEntry } from "@voip/softphone/tab_entry";

export const tabComponents = {
    ActionButton,
    ActionList,
    NoSearchResults,
    PhoneNumber,
    SearchBar,
    Tab,
    TabEntry,
};
