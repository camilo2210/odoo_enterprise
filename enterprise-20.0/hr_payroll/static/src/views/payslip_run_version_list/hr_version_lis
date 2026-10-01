import { ListRenderer } from "@web/views/list/list_renderer";

export class VersionPayrunListRenderer extends ListRenderer {
    /**
     * @override
     */
    async onCellClicked(record, column, ev, newWindow) {
        // desktop avatar clicks never get here: PayrollAvatar stops them
        if (!this.uiService.isSmall || ev.target.closest(".o_m2o_avatar")) {
            return super.onCellClicked(record, column, ev, newWindow);
        }
        this.toggleRecordSelection(record);
        ev.preventDefault();
        ev.stopPropagation();
    }
}
