import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, signal, t, useProps } from "@odoo/owl";
import { hooks, components } from "@odoo/o-spreadsheet";
import { GlobalFilterSuggestions } from "./global_filter_suggestions/global_filter_suggestions";
import { useService } from "@web/core/utils/hooks";
import { GlobalFilterItem } from "./global_filter_item/global_filter_item";

const { Section } = components;

/**
 * This is the side panel to define/edit a global filter.
 * It can be of 3 different type: text, date and relation.
 */
export class GlobalFiltersSidePanel extends Component {
    static template = "spreadsheet_edition.GlobalFiltersSidePanel";
    static components = { GlobalFilterItem, GlobalFilterSuggestions, Section };

    props = useProps({
        onCloseSidePanel: t.function().optional(),
    });

    dnd = hooks.useDragAndDropListItems();
    filtersListRef = signal.ref();

    setup() {
        this.getters = this.env.model.getters;
        this.orm = useService("orm");
        onWillStart(async () => {
            this.searchableParentRelations = await this.fetchSearchableParentRelation();
        });
    }

    get isReadonly() {
        return this.env.model.getters.isReadonly();
    }

    get filters() {
        return this.env.model.getters.getGlobalFilters();
    }

    _t(...args) {
        return _t(...args);
    }

    hasDataSources() {
        return (
            this.env.model.getters.getPivotIds().length +
            this.env.model.getters.getListIds().length +
            this.env.model.getters.getOdooChartIds().length
        );
    }

    newText() {
        this.env.replaceSidePanel("TEXT_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newSelection() {
        this.env.replaceSidePanel("SELECTION_FILTERS_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newDate() {
        this.env.replaceSidePanel("DATE_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newRelation() {
        this.env.replaceSidePanel("RELATION_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newBoolean() {
        this.env.replaceSidePanel("BOOLEAN_FILTERS_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    newNumeric() {
        this.env.replaceSidePanel("NUMERIC_FILTERS_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL");
    }

    /**
     * @param {string} id
     */
    openEditor(id) {
        const filter = this.env.model.getters.getGlobalFilter(id);
        if (!filter) {
            return;
        }
        switch (filter.type) {
            case "text":
                this.env.replaceSidePanel("TEXT_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL", {
                    id,
                });
                break;
            case "date":
                this.env.replaceSidePanel("DATE_FILTER_SIDE_PANEL", "GLOBAL_FILTERS_SIDE_PANEL", {
                    id,
                });
                break;
            case "relation":
                this.env.replaceSidePanel(
                    "RELATION_FILTER_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
            case "boolean":
                this.env.replaceSidePanel(
                    "BOOLEAN_FILTERS_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
            case "selection":
                this.env.replaceSidePanel(
                    "SELECTION_FILTERS_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
            case "numeric":
                this.env.replaceSidePanel(
                    "NUMERIC_FILTERS_SIDE_PANEL",
                    "GLOBAL_FILTERS_SIDE_PANEL",
                    { id }
                );
                break;
        }
    }

    startDragAndDrop(filter, event) {
        if (event.button !== 0) {
            return;
        }

        const rects = this.getFiltersElementsRects();
        const filtersItems = this.filters.map((filter, index) => ({
            id: filter.id,
            size: rects[index].height,
            position: rects[index].y,
        }));
        this.dnd.start("vertical", {
            draggedItemId: filter.id,
            initialMousePosition: event.clientY,
            items: filtersItems,
            scrollableContainerEl: this.filtersListRef(),
            onDragEnd: (filterId, finalIndex) => this.onDragEnd(filterId, finalIndex),
        });
    }

    getFiltersElementsRects() {
        return Array.from(this.filtersListRef().children[0].children).map((filterEl) =>
            filterEl.getBoundingClientRect()
        );
    }

    getFilterItemStyle(filter) {
        return this.dnd.itemsStyle[filter.id] || "";
    }

    onDragEnd(filterId, finalIndex) {
        const originalIndex = this.filters.findIndex((filter) => filter.id === filterId);
        const delta = finalIndex - originalIndex;
        if (filterId && delta !== 0) {
            this.env.model.dispatch("MOVE_GLOBAL_FILTER", {
                id: filterId,
                delta,
            });
        }
    }

    deleteFilter(filterId) {
        this.env.model.dispatch("REMOVE_GLOBAL_FILTER", { id: filterId });
    }

    fetchSearchableParentRelation() {
        const models = this.filters
            .filter((filter) => filter.type === "relation")
            .map((filter) => filter.modelName);
        return this.orm
            .cache({ type: "disk" })
            .call("ir.model", "has_searchable_parent_relation", [models]);
    }
}
