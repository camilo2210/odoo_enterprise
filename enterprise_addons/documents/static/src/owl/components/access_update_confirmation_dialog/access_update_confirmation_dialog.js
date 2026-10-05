import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { props, t } from "@odoo/owl";

export class AccessRightsUpdateConfirmationDialog extends ConfirmationDialog {
    static template = "documents.AccessRightsUpdateConfirmationDialog";

    props = props({
        ...confirmationDialogProps,
        destinationFolder: t.object(),
    });

    get title() {
        return _t("Moving to: %s", this.props.destinationFolder.display_name);
    }
}
