import { registry } from "@web/core/registry";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { usePlugin } from "@odoo/owl";
import { DialogPlugin } from "@web/core/dialog/dialog_plugin";

export async function SelectTaxUnitAction(_, action) {
    const dialog = usePlugin(DialogPlugin);
    dialog.add(ConfirmationDialog, {
        title: _t("Invalid Operation"),
        body: _t(
            "%(company)s is a member of a Tax Unit. Only VAT report of the whole tax unit can be sent to HMRC.",
            { company: user.activeCompany.name }
        ),
        confirm: () => {
            user.activateCompanies(action.params.companies);
        },
        cancel: () => {},
        confirmLabel: _t("Select Tax Unit"),
        cancelLabel: _t("Discard"),
    });
}

registry.category("actions").add("l10n_uk_select_tax_unit", SelectTaxUnitAction);
