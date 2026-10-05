import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { components } from "@odoo/o-spreadsheet";
import { _t } from "@web/core/l10n/translation";
import { globalFieldMatchingRegistry } from "@spreadsheet/global_filters/helpers";

import { RelatedFilters } from "../related_filters/related_filters";

import { SidepanelModelFieldSelector } from "../../../components/sidepanel_model_field_selector/sidepanel_model_field_selector";
import {
    sortModelFieldSelectorFields,
    getDataSourcePriorityFields,
    filterDataSourceField,
} from "../../../helpers/misc";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

const { Section, SidePanelCollapsible } = components;

export class RelatedFiltersSection extends Component {
    static template = "spreadsheet_edition.RelatedFiltersSection";
    static components = {
        SidePanelCollapsible,
        Section,
        RelatedFilters,
        SidepanelModelFieldSelector,
    };

    props = useProps({
        resModel: t.string(),
        dataSourceId: t.string(),
        dataSourceType: t.string(),
    });

    debugMode = usePlugin(DebugModePlugin);

    get collapsibleTitle() {
        return _t("Matching %(matching)s / %(total)s filters", {
            matching: this.numberOfMatchingFilters,
            total: this.numberOfFilters,
        });
    }

    get numberOfFilters() {
        return this.env.model.getters.getGlobalFilters().length;
    }

    get numberOfMatchingFilters() {
        let count = 0;
        const matcher = globalFieldMatchingRegistry.get(this.props.dataSourceType);
        for (const filter of this.env.model.getters.getGlobalFilters()) {
            const fieldMatching = matcher.getFieldMatching(
                this.env.model.getters,
                this.props.dataSourceId,
                filter.id
            );
            if (fieldMatching?.chain) {
                count += 1;
            }
        }
        return count;
    }

    onClickCancel(currentPanel) {
        switch (this.props.dataSourceType) {
            case "list":
                this.env.replaceSidePanel("LIST_PROPERTIES_PANEL", currentPanel, {
                    listId: this.props.dataSourceId,
                });
                break;
            case "pivot":
                this.env.replaceSidePanel("PivotSidePanel", currentPanel, {
                    pivotId: this.props.dataSourceId,
                });
                break;
            case "chart":
                this.env.replaceSidePanel("ChartPanel", currentPanel, {
                    chartId: this.props.dataSourceId,
                });
                break;
            default:
                this.env.closeSidePanel(currentPanel);
                break;
        }
    }

    filterField(field, path) {
        return filterDataSourceField(
            this.env.model.getters,
            this.props.dataSourceId,
            this.props.dataSourceType,
            field,
            path
        );
    }

    sortFields(fields) {
        const priorityFields = getDataSourcePriorityFields(
            this.env.model.getters,
            this.props.dataSourceId,
            this.props.dataSourceType
        );
        return sortModelFieldSelectorFields(fields, priorityFields);
    }

    openGlobalFilterSidePanel(_column, { fieldDef }) {
        const type = fieldDef.type;
        const panelMapping = {
            char: "TEXT_FILTER_SIDE_PANEL",
            text: "TEXT_FILTER_SIDE_PANEL",
            many2one: "RELATION_FILTER_SIDE_PANEL",
            many2many: "RELATION_FILTER_SIDE_PANEL",
            one2many: "RELATION_FILTER_SIDE_PANEL",
            datetime: "DATE_FILTER_SIDE_PANEL",
            date: "DATE_FILTER_SIDE_PANEL",
            selection: "SELECTION_FILTERS_SIDE_PANEL",
            boolean: "BOOLEAN_FILTERS_SIDE_PANEL",
            integer: "NUMERIC_FILTERS_SIDE_PANEL",
            float: "NUMERIC_FILTERS_SIDE_PANEL",
            monetary: "NUMERIC_FILTERS_SIDE_PANEL",
        };
        const panelName = panelMapping[type];
        if (!panelName) {
            return;
        }
        const initialValues = {
            label: fieldDef.string,
            field: fieldDef,
            onClickCancel: (currentPanel) => this.onClickCancel(currentPanel),
        };
        if (["many2one", "many2many", "one2many"].includes(type)) {
            initialValues.model = fieldDef.relation;
        }
        if (type === "selection") {
            initialValues.model = this.props.resModel;
        }
        this.env.openSidePanel(panelName, initialValues);
    }
}
