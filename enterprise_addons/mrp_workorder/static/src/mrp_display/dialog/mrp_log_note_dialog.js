import { useProps, t } from "@odoo/owl";
import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { HtmlField } from "@html_editor/fields/html_field";

export class MrpLogNoteDialog extends ConfirmationDialog {
    static template = "mrp_workorder.MrpLogNoteDialog";
    props = useProps({
        ...confirmationDialogProps,
        record: t.object(),
        reload: t.function().optional(),
    });
    static components = {
        ...ConfirmationDialog.components,
        HtmlField,
    };

    async _cancel() {
        this.props.record.save();
        this.props.close();
    }
}
