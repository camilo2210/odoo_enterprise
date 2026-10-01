import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { serializeDate } from "@web/core/l10n/dates";
import { getPeriodRange } from "../utils/kpi_leaderboard_period";

export const timesheetLeaderboardService = {
    async: ["getLeaderboardData"],
    dependencies: ["orm"],
    start(env, { orm }) {
        const leaderboardData = { leaderboard: [], tip: null };
        if (!browser.localStorage.getItem("leaderboardType")) {
            browser.localStorage.setItem("leaderboardType", "billing_rate");
        }
        let leaderboardType = browser.localStorage.getItem("leaderboardType") || "billing_rate";
        let currentEmployeeId = 0;

        const sortAndFilterLeaderboard = (array) => {
            const min = leaderboardType === "billing_rate" ? 0.5 : 0;
            array.sort((a, b) => b[leaderboardType] - a[leaderboardType]);
            return array.filter((line) => line[leaderboardType] > min);
        };

        const setCurrentEmployeeIndexFromLeaderboard = (array) => {
            const index = array.findIndex((object) => object.id === currentEmployeeId);
            const employeeData = array[index];
            if (index >= 0) {
                employeeData.index = index;
            }
            return employeeData;
        };

        const resetLeaderboard = () => {
            leaderboardData.leaderboard = [];
            leaderboardData.tip = null;
        };

        return {
            get leaderboardType() {
                return leaderboardType;
            },
            get showLeaderboard() {
                return "currentEmployee" in leaderboardData;
            },
            get data() {
                return leaderboardData;
            },
            async getLeaderboardData({ periodStart, fetchTips = true, kwargs = {} }) {
                const { start, stop } = getPeriodRange(periodStart);
                if (leaderboardData.anchor?.equals(start)) {
                    return;
                }
                leaderboardData.anchor = start;
                const { leaderboard, employee_id, tip } = await orm.call(
                    "res.company",
                    "get_timesheet_ranking_data",
                    [serializeDate(start), serializeDate(stop), !!fetchTips],
                    kwargs
                );
                if (!leaderboard) {
                    resetLeaderboard();
                    return;
                }
                leaderboardData.leaderboardRaw = leaderboard;
                leaderboardData.leaderboard = sortAndFilterLeaderboard(leaderboard);

                if (fetchTips && tip) {
                    leaderboardData.tip = tip;
                }

                currentEmployeeId = employee_id;
                leaderboardData.currentEmployee = setCurrentEmployeeIndexFromLeaderboard(
                    leaderboardData.leaderboard
                );
            },
            changeLeaderboardType(type) {
                leaderboardType = type;
                browser.localStorage.setItem("leaderboardType", type);
                leaderboardData.leaderboard = sortAndFilterLeaderboard(
                    leaderboardData.leaderboardRaw
                );
                leaderboardData.currentEmployee = setCurrentEmployeeIndexFromLeaderboard(
                    leaderboardData.leaderboard
                );
            },
            resetLeaderboard,
        };
    },
};

registry.category("services").add("timesheet_leaderboard", timesheetLeaderboardService);
