/** @ts-check */

import { AbstractFilterEditorSidePanel } from "./filter_editor_side_panel";
import { FilterEditorFieldMatching } from "./filter_editor_field_matching";
import { GlobalFilterInput } from "../global_filter_input/global_filter_input";

export class NumericFilterEditorSidePanel extends AbstractFilterEditorSidePanel {
    static template = "spreadsheet_edition.NumericFilterEditorSidePanel";
    static components = {
        ...AbstractFilterEditorSidePanel.components,
        FilterEditorFieldMatching,
        GlobalFilterInput,
    };

    get type() {
        return "numeric";
    }
}
