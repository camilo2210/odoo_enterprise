import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { useProps, t } from "@odoo/owl";

export class RestoreVersionConfirmationDialog extends ConfirmationDialog {
    static template = "spreadsheet_edition.RestoreVersionConfirmationDialog";
    props = useProps({
        ...confirmationDialogProps,
        makeACopy: t.function(),
    });

    async _makeACopy() {
        return this.execButton(this.props.makeACopy);
    }
}
