import { ModelFieldSelector } from "@web/core/model_field_selector/model_field_selector";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

import { Component, t, usePlugin, useProps } from "@odoo/owl";
import { FilterFieldOffset } from "../filter_field_offset";
import { sortModelFieldSelectorFields } from "../../../helpers/misc";

/**
 * @typedef {import("@spreadsheet").FieldMatching} FieldMatching
 */

export class FilterEditorFieldMatching extends Component {
    static template = "spreadsheet_edition.FilterEditorFieldMatching";
    static components = {
        ModelFieldSelector,
        FilterFieldOffset,
    };

    props = useProps({
        // See AbstractFilterEditorSidePanel fieldMatchings
        fieldMatchings: t.array(),
        selectField: t.function(),
        filterModelFieldSelectorField: t.function(),
        onOffsetSelected: t.function().optional(),
    });

    debugMode = usePlugin(DebugModePlugin);

    sortModelFieldSelectorFields = sortModelFieldSelectorFields;

    /**
     *
     * @param {FieldMatching} fieldMatch
     * @returns {string}
     */
    getModelField(fieldMatch) {
        if (!fieldMatch || !fieldMatch.chain) {
            return "";
        }
        return fieldMatch.chain;
    }
}
