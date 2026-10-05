import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { TimesheetGridMyTimesheetsModel } from "@timesheet_grid/views/timesheet_grid_my_timesheets/timesheet_grid_my_timesheets_model";

// this patch is needed because the load() method empties out the past data and prevents keeping persistent data
patch(TimesheetGridMyTimesheetsModel, {
    services: [...TimesheetGridMyTimesheetsModel.services, "timesheet_leaderboard", "timesheet_kpi"],
});
patch(TimesheetGridMyTimesheetsModel.prototype, {
    setup(params, services) {
        super.setup(params, services);
        this.timesheetLeaderboardService = services.timesheet_leaderboard;
        this.timesheetKpiService = services.timesheet_kpi;
    },

    _getAdditionalPromises(metaData) {
        const promises = super._getAdditionalPromises(metaData);
        promises.push(this._fetchData());
        return promises;
    },

    async _fetchData() {
        if (this.orm.isSample) {
            this.timesheetKpiService.resetKpiData();
            this.timesheetLeaderboardService.resetLeaderboard();
            return;
        }
        await this.timesheetKpiService.getKpiData({
            periodStart: this.navigationInfo.periodStart,
            kwargs: { context: user.context },
        });
        await this.timesheetLeaderboardService.getLeaderboardData({
            periodStart: this.navigationInfo.periodStart,
            kwargs: { context: user.context },
        });
    },
});
