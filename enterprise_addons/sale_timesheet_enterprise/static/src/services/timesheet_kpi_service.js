import { registry } from "@web/core/registry";
import { serializeDate } from "@web/core/l10n/dates";

import { getPeriodRange } from "../utils/kpi_leaderboard_period";

class TimesheetKPIService {
    constructor(orm) {
        this.data = {};
        this.orm = orm;
    }

    get showIndicators() {
        return this.data.billable_time_target > 0;
    }

    resetKpiData() {
        this.data = {};
    }

    async getKpiData({ periodStart }) {
        const { start, stop } = getPeriodRange(periodStart);
        if (this.data.anchor?.equals(start)) {
            return;
        }
        const kpiData = await this.orm.call("account.analytic.line", "get_kpi_data", [
            serializeDate(start),
            serializeDate(stop),
        ]);
        Object.assign(this.data, kpiData);
        this.data.anchor = start;
    }
}

export const timesheetKpiService = {
    dependencies: ["orm"],
    async: ["getKpiData"],
    start(env, { orm }) {
        return new TimesheetKPIService(orm);
    },
};

registry.category("services").add("timesheet_kpi", timesheetKpiService);
