import { registry } from "@web/core/registry";
import { onPatched } from "@odoo/owl";

import {
    RottingStatusBarDurationField,
    rottingStatusBarDurationField,
} from "@mail/js/rotting_mixin/rotting_statusbar";

export class TaskStatusBarDurationField extends RottingStatusBarDurationField {
    setup() {
        super.setup();
        onPatched(() => this._saveLatestVisitedRecord());
    }

    _saveLatestVisitedRecord() {
        const { record } = this.props;
        if (this._isTimesheetRecord(record)) {
            localStorage.setItem(
                "timesheet.preFilledForm",
                JSON.stringify({
                    ...this._getPreFilledData(record),
                })
            );
        }
    }

    _isTimesheetRecord(record) {
        return (
            record.data.active &&
            record.data.allow_timesheets &&
            !record.data.is_template &&
            !record.data.has_template_ancestor
        );
    }

    _getPreFilledData(record) {
        return {
            task_id: record.resId,
        };
    }
}

export const taskStatusBarDurationField = {
    ...rottingStatusBarDurationField,
    component: TaskStatusBarDurationField,
};

registry.category("fields").add("task_rotting_statusbar_duration", taskStatusBarDurationField);
