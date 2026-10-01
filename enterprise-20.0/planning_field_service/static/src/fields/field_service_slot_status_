import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { statusBarField, StatusBarField } from "@web/views/fields/statusbar/statusbar_field";

export class FieldServiceSlotStatusBarField extends StatusBarField {
    setup() {
        super.setup();
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
    }

    async selectItem(item) {
        if (
            item.value == "4_completed" &&
            this.props.record.data.partner_id &&
            this.props.record.data.start_datetime &&
            this.props.record.data.end_datetime
        ) {
            this.rootRef().querySelector("button[data-value='4_completed']")?.blur();
            this.dialogService.add(ConfirmationDialog, {
                body: _t("Are you sure you want to mark this shift as complete?"),
                confirmLabel: _t("Complete"),
                confirm: async () => {
                    await this.props.record.save();
                    await this.orm.call(
                        this.props.record.resModel,
                        "action_complete",
                        [this.props.record.resId],
                        { from_status_bar: true }
                    );
                    await this.props.record.load();
                },
                cancel: () => {},
            });
        } else {
            await super.selectItem(item);
        }
    }
}

export const fieldServiceSlotStatusBar = {
    ...statusBarField,
    component: FieldServiceSlotStatusBarField,
    additionalClasses: ["o_field_statusbar"],
    fieldDependencies: [
        { name: "partner_id", type: "many2one" },
        { name: "start_datetime", type: "datetime" },
        { name: "end_datetime", type: "datetime" },
    ],
};

registry.category("fields").add("field_service_slot_status_bar", fieldServiceSlotStatusBar);
