import { Component, t, useProps, signal, usePlugin, onWillStart } from "@odoo/owl";
import { NotificationPlugin } from "@web/core/notifications/notification_plugin";
import { Many2One } from "@web/views/fields/many2one/many2one";
import { registry } from "@web/core/registry";
import { ORM } from "@web/core/orm_plugin";
import { _t } from "@web/core/l10n/translation";


export class WorkingFilePage extends Component {
    static template = "account_reports_spreadsheet.WorkingFilePage";
    static components = {
        Many2One,
    };

    props = useProps({
        workingFileId: t.number().optional(),
        onSpreadsheetSelected: t.function(),
    });
    notification = usePlugin(NotificationPlugin);
    orm = usePlugin(ORM);
    model = "account.working.file.sheet";

    setup() {
        this.currentSelectedWorkingFile = signal(false);
        this.invalidFieldWorkingfile = signal(false);

        this.props.onSpreadsheetSelected({
            getOpenSpreadsheetAction: this.getOpenSpreadsheetAction.bind(this),
        });

        onWillStart(async () => {
            if (this.props.workingFileId) {
                const result = await this.orm.read(
                    "account.return",
                    [this.props.workingFileId],
                    ["id", "display_name"]
                );
                if (result.length) {
                    this.currentSelectedWorkingFile.set(result[0]);
                }
            }
        });
    }

    get workingFileFieldProps() {
        return {
            relation: "account.return",
            domain: () => [["type_id.category", "=", "audit"]],
            update: (args) => {
                this.currentSelectedWorkingFile.set(args);
            },
            value: this.currentSelectedWorkingFile(),
            canOpen: false,
            canCreate: false,
            canCreateEdit: false,
            canQuickCreate: false,
        };
    }

    async getOpenSpreadsheetAction() {
        const workingFileData = this.workingFileData;
        this.invalidFieldWorkingfile.set(!workingFileData.workingFileId);
        if (this.invalidFieldWorkingfile()) {
            this._displayInvalidFieldNotification();
            return;
        }
        const result = await this.orm.read(
            "account.return",
            [workingFileData.workingFileId],
            ["working_file_sheet_id"]
        );
        const workingFileSheetId = result[0].working_file_sheet_id;
        if (!workingFileSheetId) {
            const action = await this.orm.call(this.model, "action_open_new_spreadsheet", [], {
                vals: {
                    account_return_id: workingFileData.workingFileId,
                },
            });
            action.params.is_new_spreadsheet = true;
            return action;
        }

        const action = await this.orm.call(this.model, "action_open_spreadsheet", [
            [workingFileSheetId[0]],
        ]);

        return action;
    }

    get workingFileData() {
        return {
            workingFileId: this.currentSelectedWorkingFile()?.id,
        };
    }

    _displayInvalidFieldNotification() {
        return this.notification.add(_t("Missing required fields"), { type: "danger" });
    }
}

registry
    .category("spreadsheet_selector_dialog_pages_component")
    .add("WorkingFilePage", WorkingFilePage);
