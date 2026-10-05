import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class BatchDeclarationWarningDialog extends ConfirmationDialog {
    static template = "l10n_be_hr_payroll.BatchDeclarationWarningDialog";
}

function batchDeclarationCertificateWarning() {
    const dialog = useService("dialog");
    const action = useService("action");
    dialog.add(BatchDeclarationWarningDialog, {
        title: _t("Batch Declaration Warning"),
        confirmLabel: _t("Go to Settings"),
        confirm: () => action.doAction("hr_payroll.action_hr_payroll_configuration"),
        cancelLabel: _t("Discard"),
        cancel: () => {},
    });
}

registry.category("actions").add("l10n_be_hr_payroll.batch_declaration_certificate_warning", batchDeclarationCertificateWarning);
