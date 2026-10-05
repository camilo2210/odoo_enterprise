/** @ts-check */

import { proxy } from "@odoo/owl";
import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";

import { components } from "@odoo/o-spreadsheet";
import { GlobalFilterInput } from "../global_filter_input/global_filter_input";

const { SelectionInput } = components;

/**
 * This is the side panel to define/edit a global filter of type "text".
 */
export class TextFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.TextFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        FilterEditorFieldMatching,
        SelectionInput,
        GlobalFilterInput,
    };

    setup() {
        super.setup();
        this.state = proxy({
            rangeRestriction: !!this.store.filter.rangesOfAllowedValues,
        });
    }

    get type() {
        return "text";
    }

    toggleRangeRestriction(isChecked) {
        if (!isChecked) {
            this.onRangeChanged([]);
            this.store.update({ rangesOfAllowedValues: undefined });
        }
        this.state.rangeRestriction = isChecked;
    }

    onRangeChanged(ranges) {
        this.ranges = ranges;
    }

    onRangeConfirmed() {
        if (this.state.rangeRestriction && this.ranges.length) {
            const sheetId = this.env.model.getters.getActiveSheetId();
            const rangesOfAllowedValues = this.ranges.map((range) =>
                this.env.model.getters.getRangeFromSheetXC(sheetId, range)
            );
            this.ranges = [];
            this.store.update({ rangesOfAllowedValues });
        }
    }
}
