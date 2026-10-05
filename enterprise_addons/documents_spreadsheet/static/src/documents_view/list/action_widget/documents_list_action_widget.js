import { DocumentsListActionWidget } from "@documents/views/list/action_widget/documents_list_action_widget";
import { patch } from "@web/core/utils/patch";

patch(DocumentsListActionWidget.prototype, {
    get actionItems() {
        const items = super.actionItems;
        const downloadAction = items.find((a) => a.name === "download");
        const superIsVisible = downloadAction.isVisible;
        downloadAction.isVisible = () =>
            superIsVisible() && this.props.record.data.handler !== "spreadsheet";
        return items;
    },
});
