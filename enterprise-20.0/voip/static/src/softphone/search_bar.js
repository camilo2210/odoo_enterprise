import { Component, computed, useProps, signal, t, useEffect } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useDebounced } from "@web/core/utils/timing";

/**
 * Search bar component used in softphone tabs to filter entries.
 */
export class SearchBar extends Component {
    static template = "voip.SearchBar";
    props = useProps({
        state: t.object(),
        onInputSearch: t.function(),
        onClickBack: t.function().optional(),
        placeholder: t.string().optional(_t("Search…")),
        trailingIcon: t.string().optional(),
        onTrailingIconClick: t.function().optional(),
        trailingIconTitle: t.string().optional(),
    });
    showPendingIcon = signal(false);

    setup() {
        this.voip = useService("voip");
        this.softphone = this.voip.softphone;
        this.showPendingSearchIcon = useDebounced(() => this.showPendingIcon.set(true), 400);
        const hasPendingRequest = computed(() => this.voip.hasPendingRequest);
        useEffect(() => {
            if (hasPendingRequest()) {
                this.showPendingSearchIcon();
            } else {
                this.showPendingSearchIcon.cancel();
                this.showPendingIcon.set(false);
            }
        });
    }

    /**
     * When an RPC is pending, the search icon is replaced with a spinner.
     *
     * @returns {string}
     */
    get searchBarIcon() {
        if (this.showPendingIcon()) {
            return "autorenew";
        }
        return this.props.trailingIcon || "search";
    }

    /**
     * @returns {string}
     */
    get searchBarIconClasses() {
        return this.showPendingIcon() ? "oi-spin" : "";
    }

    get trailingIconTitle() {
        return this.props.trailingIconTitle || "";
    }
}
