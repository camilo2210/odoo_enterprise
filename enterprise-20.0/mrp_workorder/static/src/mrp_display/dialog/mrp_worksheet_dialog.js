import { useProps, t } from "@odoo/owl";
import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import DocumentViewer from "@mrp_workorder/components/viewer";
import { HtmlField } from "@html_editor/fields/html_field";

export class MrpWorksheetDialog extends ConfirmationDialog {
    props = useProps({
        ...confirmationDialogProps,
        body: t.any().optional(),
        worksheetData: t.or([t.object(), t.boolean()]),
        record: t.object(),
    });
    static template = "mrp_workorder.MrpWorksheetDialog";
    static components = {
        ...ConfirmationDialog.components,
        DocumentViewer,
        HtmlField,
    };

    get htmlInfo() {
        return {
            name: "note",
            record: this.props.record,
            readonly: true,
            embeddedComponents: true,
        };
    }
}
