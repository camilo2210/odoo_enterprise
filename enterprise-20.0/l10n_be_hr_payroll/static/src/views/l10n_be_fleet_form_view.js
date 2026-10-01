import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { FleetFormController } from "@fleet/js/fleet_form";
import { EmployeeFormController } from "@hr/views/form_view";
import { formView } from "@web/views/form/form_view";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";

/**
 * Ask the user to confirm a change landing on a quarter already declared to the ONSS.
 */
function confirmDmfaImpact(dialogService) {
    return new Promise((resolve) => {
        dialogService.add(ConfirmationDialog, {
            title: _t("Update Company Car"),
            body: _t(
                "Changing a car on a period already covered by a payslip and a DMFA will result in an ONSS fine. Do you confirm?"
            ),
            confirmLabel: _t("Confirm"),
            confirm: () => resolve(true),
            cancelLabel: _t("Discard"),
            cancel: () => resolve(false),
            dismiss: () => resolve(false),
        });
    });
}

patch(EmployeeFormController.prototype, {
    /**
     * @override
     **/
    async onWillSaveRecord(record, changes) {
        // A car swap on a declared version is what the ONSS fines, ask before saving it
        const requiresPrompt =
            record.resId &&
            "car_id" in changes &&
            record.data.version_id &&
            (await this.orm.call("fleet.vehicle", "version_requires_prompt", [
                changes.car_id,
                record.data.version_id.id,
            ]));
        if (requiresPrompt && !(await confirmDmfaImpact(this.dialogService))) {
            // Wipe the unsaved changes from the UI
            record.discard();
            return false;
        }
        return super.onWillSaveRecord(...arguments);
    },
});

export class L10nBEFleetFormController extends FleetFormController {
    /**
     * @override
     **/
    async onWillSaveRecord(record, changes) {
        // The server owns the list of fields impacting the DMFA, one call is enough
        const requiresPrompt =
            record.resId &&
            (await this.orm.call("fleet.vehicle", "requires_prompt", [
                record.resId,
                Object.keys(changes),
            ]));
        if (requiresPrompt && !(await confirmDmfaImpact(this.dialogService))) {
            // Wipe the unsaved changes from the UI
            record.discard();
            return false;
        }
        return super.onWillSaveRecord(...arguments);
    }
}

export const l10nBEFleetFormView = {
    ...formView,
    Controller: L10nBEFleetFormController,
};

registry.category("views").add("l10n_be_fleet_form", l10nBEFleetFormView);
