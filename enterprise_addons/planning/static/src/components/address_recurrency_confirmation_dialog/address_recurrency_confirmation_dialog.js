import { useProps, t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";

export class AddressRecurrencyConfirmationDialog extends ConfirmationDialog {
    static template = "planning.AddressRecurrencyConfirmationDialog";
    props = useProps({
        ...confirmationDialogProps,
        body: t.string().optional(""),
        onChangeRecurrenceUpdate: t.function(),
        selected: t.string(),
        cancel: t.function().optional(() => () => {}),
        title: t.any().optional(_t("Delete Recurring Shift")),
    });
}
