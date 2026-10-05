import { patch } from "@web/core/utils/patch";
import { serializeDate } from "@web/core/l10n/dates";
import { TimesheetGridModel } from "@timesheet_grid/views/timesheet_grid/timesheet_grid_model";

patch(TimesheetGridModel.prototype, {
    getTimesheetWorkingHoursPromises(metaData) {
        const promises = super.getTimesheetWorkingHoursPromises(metaData);
        promises.push(this._fetchWorkingHoursData(metaData, "so_line"));
        promises.push(this._fetchAllTimesheetM2OAvatarTargetLimitData(metaData));
        promises.push(this._fetchTargetLimitIndicator(metaData));
        return promises;
    },

    get targetLeftData() {
        return this.data.targetLeft;
    },

    get targetLimitsSetData() {
        return this.data.targetLimitsSet;
    },

    async _getInitialData(metaData) {
        const initialData = await super._getInitialData(metaData);
        initialData.data.targetLeft = {};
        initialData.data.targetLimitsSet = false;
        return initialData;
    },

    async _fetchTargetLimitIndicator({ data, searchParams }) {
        const targetLimitsSet = await this.orm.call(
            this.employeeField.relation,
            "get_timesheet_target_show_rates_value"
        );
        data.targetLimitsSet = targetLimitsSet;
    },

    async _fetchAllTimesheetM2OAvatarTargetLimitData({ data, sectionField, rowFields }) {
        if (
            !this.employeeField ||
            this.navigationInfo.contains(this.today) ||
            this.navigationInfo.periodStart.startOf("day") > this.today.startOf("day")
        ) {
            return {};
        }
        const fieldValues = this._getFieldValuesInSectionAndRows(
            this.employeeField,
            sectionField,
            rowFields,
            data
        );
        const nonEmptyValues = fieldValues.filter((v) => v !== false);
        if (!nonEmptyValues.length) {
            return {};
        }
        const resultTargetLeft = await this.orm.call(
            this.employeeField.relation,
            "get_timesheet_and_target_hours_for_employees",
            [
                nonEmptyValues,
                serializeDate(this.navigationInfo.periodStart),
                serializeDate(this.navigationInfo.periodEnd),
            ]
        );
        data.targetLeft.employee_id = resultTargetLeft;
    },
});
