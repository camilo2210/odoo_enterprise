import { patch } from "@web/core/utils/patch";
import { TimesheetAssistantModel } from "@timesheet_grid/components/aw_timesheet/aw_timesheet_model";

patch(TimesheetAssistantModel.prototype, {
    /** @override */
    async loadAssistantData() {
        const data = await super.loadAssistantData();
        this.isAgentAvailable = data.is_agent_available;
        return data;
    },
});
