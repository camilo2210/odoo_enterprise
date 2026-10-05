import { Component, onWillStart, proxy, usePlugin, t, useProps } from "@odoo/owl";
import { components, stores } from "@odoo/o-spreadsheet";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";
import { InlineModelFieldSelector } from "../../../components/sidepanel_model_field_selector/sidepanel_model_field_selector";

import { FilterEditorStore } from "../../filter_editor_store";
import { FilterFieldOffset } from "../filter_field_offset";
import {
    sortModelFieldSelectorFields,
    getDataSourcePriorityFields,
    filterDataSourceField,
} from "../../../helpers/misc";
import { useService } from "@web/core/utils/hooks";

const { Section } = components;
const { useLocalStore } = stores;

export class RelatedFilters extends Component {
    static template = "spreadsheet_edition.RelatedFilters";

    props = useProps({
        resModel: t.string(),
        dataSourceId: t.string(),
        dataSourceType: t.string(),
    });

    static components = { InlineModelFieldSelector, Section, FilterFieldOffset };

    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.editedFilters = proxy({});
        this.fieldsService = useService("field");
        this.stores = {};
        for (const filter of this.env.model.getters.getGlobalFilters()) {
            this.stores[filter.id] = useLocalStore(
                FilterEditorStore,
                { id: filter.id },
                filter.type
            );
            onWillStart(async () => {
                await this.stores[filter.id].loadData;
            });
        }
    }

    get canSave() {
        return Object.values(this.stores).every((store) => store.canSave);
    }

    fieldMatchingIsDefined(filterId, fieldMatching) {
        return fieldMatching.fieldMatch.chain !== undefined || this.editedFilters[filterId]?.linked;
    }

    getFieldMatching(filterId) {
        const fieldMatching = this.stores[filterId].fieldsMatching.find(
            (fieldMatching) =>
                fieldMatching.payload().id === this.props.dataSourceId &&
                fieldMatching.payload().type === this.props.dataSourceType
        );
        return fieldMatching;
    }

    updateFieldMatchingOffset(filterId, fieldMatchingId, offset) {
        this.stores[filterId].updateFieldMatchingOffset(fieldMatchingId, offset);
        this.save();
    }

    selectField(filterId, fieldMatchingId, path, field) {
        this.stores[filterId].updateFieldMatching(fieldMatchingId, path, field);
        this.save();
    }

    async removeFieldMatching(filterId, fieldMatchingId) {
        const path = this.getFieldMatching(filterId).fieldMatch.chain;
        this.editedFilters[filterId] = { linked: false, lastFieldMatchingId: fieldMatchingId };
        if (path !== undefined) {
            const field = await this.fieldsService.loadPath(this.props.resModel, path);
            this.editedFilters[filterId].path = path;
            this.editedFilters[filterId].field =
                field.modelsInfo.at(-1).fieldDefs[field.names.at(-1)];
        }
        this.stores[filterId].updateFieldMatching(fieldMatchingId, null);
        this.save();
    }

    linkFieldMatching(filterId) {
        if (!this.editedFilters[filterId]) {
            this.editedFilters[filterId] = { linked: true };
            return;
        }
        this.selectField(
            filterId,
            this.editedFilters[filterId].lastFieldMatchingId,
            this.editedFilters[filterId].path,
            this.editedFilters[filterId].field
        );
        this.editedFilters[filterId] = { ...this.editedFilters[filterId], linked: true };
    }

    filterFields(filterId, field, path, coModel) {
        return (
            this.stores[filterId].filterModelFieldSelectorField(field, path, coModel) &&
            filterDataSourceField(
                this.env.model.getters,
                this.props.dataSourceId,
                this.props.dataSourceType,
                field,
                path
            )
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

    save() {
        if (!this.canSave) {
            return;
        }
        const fieldMatchings = {};
        for (const filterId in this.stores) {
            fieldMatchings[filterId] = this.getFieldMatching(filterId).fieldMatch;
        }
        this.env.model.dispatch("SET_DATASOURCE_FIELD_MATCHING", {
            dataSourceId: this.props.dataSourceId,
            fieldMatchings,
            dataSourceType: this.props.dataSourceType,
        });
    }
}
