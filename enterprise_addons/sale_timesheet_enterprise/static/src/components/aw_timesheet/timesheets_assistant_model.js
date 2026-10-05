import { omit } from "@web/core/utils/objects";
import { patch } from "@web/core/utils/patch";
import { TimesheetAssistantModel } from "@timesheet_grid/components/aw_timesheet/aw_timesheet_model";

patch(TimesheetAssistantModel.prototype, {
    get defaultDataValues() {
        return {
            ...omit(super.defaultDataValues, "timesheets"),
            billableTimesheets: [],
            nonBillableTimesheets: [],
            billableTime: 0,
            nonBillableTime: 0,
            billablePercentage: 0,
            nonBillablePercentage: 0,
        };
    },

    getTimesheets(data = this.data) {
        return [...data.billableTimesheets, ...data.nonBillableTimesheets];
    },

    async loadTimesheets(data = this.data) {
        data.billableTimesheets = [];
        data.nonBillableTimesheets = [];
        data.billableTime = 0;
        data.nonBillableTime = 0;
        await super.loadTimesheets(data);
    },

    refreshTimesheetsOnAdd(timesheet, data = this.data) {
        if (timesheet.so_line) {
            data.billableTimesheets.push(timesheet);
            data.billableTime += timesheet.unit_amount;
        } else {
            data.nonBillableTimesheets.push(timesheet);
            data.nonBillableTime += timesheet.unit_amount;
        }
        data.totalTime += timesheet.unit_amount;
        this._computeTimePercentages(data);
    },

    refreshTimesheetsOnRemove(timesheetId) {
        let timesheetToRemove = null;
        let index = this.data.billableTimesheets.findIndex((t) => t.id === timesheetId);
        if (index >= 0) {
            timesheetToRemove = this.data.billableTimesheets[index];
            this.data.billableTime -= timesheetToRemove.unit_amount;
            this.data.billableTimesheets.splice(index, 1);
            this.data.totalTime -= timesheetToRemove.unit_amount;
        } else {
            index = this.data.nonBillableTimesheets.findIndex((t) => t.id === timesheetId);
            if (index >= 0) {
                timesheetToRemove = this.data.nonBillableTimesheets[index];
                this.data.nonBillableTime -= timesheetToRemove.unit_amount;
                this.data.nonBillableTimesheets.splice(index, 1);
                this.data.totalTime -= timesheetToRemove.unit_amount;
            }
        }
        this._computeTimePercentages();
        return timesheetToRemove;
    },

    _computeTimePercentages(data = this.data) {
        if (data.totalTime) {
            data.billablePercentage = (data.billableTime * 100) / data.totalTime;
            data.nonBillablePercentage = (data.nonBillableTime * 100) / data.totalTime;
        } else {
            data.billablePercentage = 0;
            data.nonBillablePercentage = 0;
        }
    },

    getLocalConfigValsOnTake(params) {
        const res = super.getLocalConfigValsOnTake(params);
        if (params.billable != null) {
            res.billable = params.billable;
        }
        return res;
    },

    refreshTimesheetsOnUpdate(timesheet) {
        let oldTimesheet;
        let index = this.data.billableTimesheets.findIndex((t) => t.id === timesheet.id);
        if (index >= 0) {
            oldTimesheet = this.data.billableTimesheets[index];
            this.data.billableTime -= oldTimesheet.unit_amount;
            this.data.totalTime += timesheet.unit_amount - oldTimesheet.unit_amount;
            if (timesheet.so_line) {
                this.data.billableTimesheets[index] = timesheet;
                this.data.billableTime += timesheet.unit_amount;
            } else {
                this.data.billableTimesheets.splice(index, 1);
                this.data.nonBillableTimesheets.push(timesheet);
                this.data.nonBillableTime += timesheet.unit_amount;
            }
        } else {
            index = this.data.nonBillableTimesheets.findIndex((t) => t.id === timesheet.id);
            if (index < 0) {
                return null;
            }
            oldTimesheet = this.data.nonBillableTimesheets[index];
            this.data.totalTime += timesheet.unit_amount - oldTimesheet.unit_amount;
            this.data.nonBillableTime -= oldTimesheet.unit_amount;
            if (timesheet.so_line) {
                this.data.nonBillableTimesheets.splice(index, 1);
                this.data.billableTimesheets.push(timesheet);
                this.data.billableTime += timesheet.unit_amount;
            } else {
                this.data.nonBillableTimesheets[index] = timesheet;
                this.data.nonBillableTime += timesheet.unit_amount;
            }
        }
        this._computeTimePercentages();
        return oldTimesheet;
    },
});
