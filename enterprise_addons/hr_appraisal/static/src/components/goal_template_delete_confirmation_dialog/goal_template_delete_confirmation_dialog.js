import { useProps, t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    confirmationDialogProps,
    deleteConfirmationMessage,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";

export class GoalTemplateDeleteConfirmationDialog extends ConfirmationDialog {
    static template = "hr_appraisal.GoalTemplateDeleteConfirmationDialog";

    props = useProps({
        ...confirmationDialogProps,
        hasChildren: t.boolean(),
        confirmAllLabel: t.string().optional(_t("Delete with children")),
        confirmAll: t.function(),
        title: t.any().optional(_t("Bye-bye, record!")),
        body: t.string().optional(deleteConfirmationMessage),
        confirmLabel: t.string().optional(_t("Delete")),
        cancel: t.function().optional(
            () => () => {
                // `ConfirmationDialog` needs this prop to display the cancel
                // button but we do nothing on cancel.
            }
        ),
        cancelLabel: t.string().optional(_t("No, keep it")),
    });
}
