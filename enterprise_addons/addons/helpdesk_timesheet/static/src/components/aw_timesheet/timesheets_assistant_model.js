import { patch } from "@web/core/utils/patch";
import { TimesheetAssistantModel } from "@timesheet_grid/components/aw_timesheet/aw_timesheet_model";

patch(TimesheetAssistantModel.prototype, {
    getLocalConfigValsOnTake(params) {
        const res = super.getLocalConfigValsOnTake(params);
        if (params.helpdesk_ticket_id) {
            res.helpdesk_ticket_id = this._getResId(params.helpdesk_ticket_id);
        }
        return res;
    },

    getSuggestionParams(groupKey, title, start = false, groupBy) {
        const res = super.getSuggestionParams(...arguments);
        if (res === false) {
            return false;
        }
        let record;
        if (groupBy === "timeline") {
            record = this.data.recordsByStart[start];
        } else {
            record = this.data.grouped[groupKey]?.suggestions?.[title];
        }
        if (record && record.source_model === "helpdesk.ticket" && record.source_id) {
            const { project_id } = JSON.parse(groupKey);
            const ticketData = this.projectAndTaskData?.["helpdesk.ticket"]?.[record.source_id];
            // only link the ticket if it actually belongs to this project in the database.
            // this prevents server crashes when adding the timesheet on projects pulled from memory.
            if (
                this.isProjectAllowsTimesheets(project_id) &&
                project_id === ticketData?.project_id
            ) {
                res.helpdesk_ticket_id = record.source_id;
            }
        }
        return res;
    },
});
