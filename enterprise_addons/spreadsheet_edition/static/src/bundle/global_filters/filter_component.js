import * as spreadsheet from "@odoo/o-spreadsheet";

import { Component, onWillStart, onWillUnmount, t, useProps } from "@odoo/owl";
import { getFacetInfo } from "@spreadsheet/global_filters/helpers";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";

const { Menu } = spreadsheet;

class FiltersTooltip extends Component {
    static template = "spreadsheet_edition.FiltersTooltip";
    static components = { Dialog };

    props = useProps({
        model: t.object(),
        onMouseLeave: t.function(),
        onMouseEnter: t.function(),
        onClick: t.function(),
        close: t.function().optional(),
    });

    setup() {
        this.facets = [];
        this.nameService = useService("name");
        onWillStart(this.computeFacets.bind(this));
    }

    async computeFacets() {
        const filters = this.props.model.getters
            .getGlobalFilters()
            .filter((filter) => this.props.model.getters.isGlobalFilterActive(filter.id));
        this.facets = await Promise.all(filters.map((filter) => this.getFacetFor(filter)));
    }

    async getFacetFor(filter) {
        const filterValues = this.props.model.getters.getGlobalFilterValue(filter.id);
        return getFacetInfo(this.env, filter, filterValues, this.props.model.getters);
    }
}

export class FilterComponent extends Component {
    static template = "spreadsheet_edition.FilterComponent";
    static components = { Menu };

    setup() {
        this.popover = usePopover(FiltersTooltip, { position: "bottom" });
        this.dialog = useService("dialog");

        onWillUnmount(() => {
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
            }
        });
    }

    toggleSidePanel() {
        this.env.toggleSidePanel("GLOBAL_FILTERS_SIDE_PANEL");
    }

    get activeFilter() {
        return this.env.model.getters.getActiveFilterCount();
    }

    openPopover(ev) {
        if (this.activeFilter) {
            this.popover.open(ev.currentTarget, {
                model: this.env.model,
                onMouseEnter: () => clearTimeout(this.timeoutId),
                onMouseLeave: this.closePopover.bind(this),
                onClick: this.toggleSidePanel.bind(this),
            });
        }
    }

    closePopover() {
        this.timeoutId = setTimeout(() => this.cleanupPopover(), 300);
    }

    cleanupPopover() {
        this.timeoutId = undefined;
        this.popover.close();
    }
}
