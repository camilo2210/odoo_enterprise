import { registry } from "@web/core/registry";

import { AbstractSpreadsheetAction } from "@spreadsheet_edition/bundle/actions/abstract_spreadsheet_action";

export class AccountWorkingFileSpreadsheetAction extends AbstractSpreadsheetAction {
    static template = "account_reports_spreadsheet.SpreadsheetAction";

    resModel = "account.working.file.sheet";
    setup() {
        super.setup();

        // We need to do this in order to avoid letting preprocessing action create new sheets.
        // It is handled by our preprocessing callback.
        this.isNewSpreadsheet = this.isEmptySpreadsheet;
        this.isEmptySpreadsheet = true;
    }

    async _setupPreProcessingCallbacks() {
        if (this.params.preProcessingAction) {
            this.params.preProcessingActionData = {
                subActionData: this.params.preProcessingActionData,
                subAction: this.params.preProcessingAction,
            };
            this.params.preProcessingAction = "workingFilePreprocessingAction";
        }
        if (this.params.preProcessingAsyncAction) {
            this.params.preProcessingAsyncActionData = {
                subActionData: this.params.preProcessingAsyncActionData,
                subAction: this.params.preProcessingAsyncAction,
            };
            this.params.preProcessingAsyncAction = "workingFilePreprocessingAction";
        }

        await super._setupPreProcessingCallbacks();
    }
}

registry
    .category("actions")
    .add("action_open_working_file_sheet", AccountWorkingFileSpreadsheetAction, { force: true });
