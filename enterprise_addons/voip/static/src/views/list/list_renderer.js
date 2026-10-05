import { ListRenderer } from "@web/views/list/list_renderer";

export class VoipResultLineListRenderer extends ListRenderer {
    get hasOpenFormViewColumn() {
        return false;
    }
    get hasOptionalOpenFormViewColumn() {
        return false;
    }
    /**
     * Clicking anywhere on a result row toggles its selection: the row IS a
     * checkbox for this list, there is nothing else to edit.
     * @override
     */
    onCellClicked(record, column, ev) {
        if (ev.target.closest("input")) {
            return;
        }
        record.update({ selected: !record.data.selected });
    }
}
