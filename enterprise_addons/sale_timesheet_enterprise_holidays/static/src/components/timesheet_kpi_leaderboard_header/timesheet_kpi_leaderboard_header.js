import { Domain } from "@web/core/domain";
import { patch } from "@web/core/utils/patch";

import { TimesheetKpiLeaderboardHeader } from "@sale_timesheet_enterprise/components/timesheet_kpi_leaderboard_header/timesheet_kpi_leaderboard_header";

patch(TimesheetKpiLeaderboardHeader.prototype, {
    getFieldInfo(fieldName) {
        const fieldInfo = super.getFieldInfo(fieldName);
        if (fieldName === "task_id") {
            fieldInfo.domain = Domain.and([
                fieldInfo.domain || [],
                [["is_timeoff_task", "=", false]],
            ]).toString();
        }
        return fieldInfo;
    },
});
