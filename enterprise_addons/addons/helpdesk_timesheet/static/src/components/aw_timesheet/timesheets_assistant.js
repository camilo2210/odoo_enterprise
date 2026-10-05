import { patch } from "@web/core/utils/patch";
import { TimesheetsAssistant } from "@timesheet_grid/components/aw_timesheet/aw_timesheet";

patch(TimesheetsAssistant.prototype, {
    get selectedData() {
        const res = super.selectedData;

        if (this.selectedTimesheet) {
            return res;
        }

        for (const row of this.state.selectedRows) {
            const { groupKey, title, start } = JSON.parse(row);
            const params = this.model.getSuggestionParams(
                groupKey,
                title,
                start,
                this.state.groupBy
            );

            if (params.helpdesk_ticket_id) {
                const { project_id } = JSON.parse(groupKey);
                if (project_id === res.project_id && !res.task_id) {
                    res.helpdesk_ticket_id = params.helpdesk_ticket_id;
                    break;
                }
            }
        }

        return res;
    },
});
