/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { EmployeeFormController } from "@hr/views/form_view";
import { VersionUpdateDialog } from "./version_update_dialog";

const EXCLUDED_FIELDS = ["contract_date_end", "resource_calendar_id"];

patch(EmployeeFormController.prototype, {
    setup() {
        super.setup();
        this.versionChoice = null;
    },

    async onRecordChanged(record, changes) {
        await super.onRecordChanged(...arguments);

        const modifiedFieldNames = Object.keys(changes || {});
        const isExcludedEditOnly = modifiedFieldNames.length > 0 && modifiedFieldNames.every((fieldName) => EXCLUDED_FIELDS.includes(fieldName));

        const versionId = record.data.version_id?.id
        if (!record.resId || this.versionChoice || isExcludedEditOnly || !versionId) {
            return;
        }

        const status = await this.orm.call(
            "hr.version",
            "action_check_version_status",
            [[versionId]]
        );

        if (!status.is_last_version || !status.valid_payslips_count) {
            return;
        }

        const choice = await new Promise((resolve) => {
            this.dialogService.add(VersionUpdateDialog, {
                payslipsCount: status.valid_payslips_count,
                confirm: (selection) => resolve(selection),
                cancel: () => resolve(null),
                close: () => resolve(null),
            });
        });

        if (!choice) {
            record.discard();  // User cancel -> discard the chnages
        } else {
            this.versionChoice = choice;  // User select -> cache the choice locally
        }
    },

    async save() {
        const record = this.model.root;

        if (this.versionChoice?.mode === "create_new_version") {
            const versionId = record.data.version_id?.id;

            if (versionId) {
                record._skipContractEndDialog = true;

                const changes = record._getChanges()
                const filteredChanges = Object.fromEntries(
                    Object.entries(changes).filter(([key]) => !EXCLUDED_FIELDS.includes(key))
                );

                await this.orm.call(
                    "hr.version",
                    "action_create_version_from_update",
                    [[versionId], this.versionChoice.dateStart, filteredChanges]
                );

                this.versionChoice = null;
                delete record._skipContractEndDialog;

                await record.discard(); // Reset changes on current record
                await this.model.load(); // Reload model to the newly created version
                return true;
            }
        }

        const saved = await super.save();
        if (saved) {
            this.versionChoice = null;
        }
        return saved;
    },

    discard() {
        this.versionChoice = null;
        return super.discard(...arguments);
    }
});
