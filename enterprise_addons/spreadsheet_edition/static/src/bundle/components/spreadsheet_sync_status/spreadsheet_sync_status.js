import { Component, t, useProps } from "@odoo/owl";

export class SpreadsheetSyncStatus extends Component {
    static template = "spreadsheet_edition.SpreadsheetSyncStatus";

    props = useProps({
        model: t.object().optional(),
    });

    get isSynced() {
        return this.props.model && this.props.model.getters.isFullySynchronized();
    }
}
