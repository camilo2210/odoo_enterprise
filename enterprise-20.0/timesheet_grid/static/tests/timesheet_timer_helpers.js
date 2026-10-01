import { beforeEach } from "@odoo/hoot";
import { advanceTime, tick } from "@odoo/hoot-mock";
import { startServer } from "@mail/../tests/mail_test_helpers";
import { onRpc, serverState } from "@web/../tests/web_test_helpers";
import { registry } from "@web/core/registry";
import { roundTimeSpent } from "@timesheet_grid/utils/timer";

export function setupTimesheetEnvironment() {
    const env = {
        pyEnv: null,
        sessionData: {},
        employeeData: {},
    };

    beforeEach(async () => {
        env.employeeData = { id: serverState.userId, name: "John Timesheet", working_hours: 8 };
        env.sessionData = {
            timesheet_systray_employee_data: {
                id: serverState.userId,
                name: "John Timesheet",
                working_hours: 8,
            },
            display_timesheets_systray: true,
            display_timesheets_assistant: false,
            timesheet_rounding_values: {
                minimum: 15,
                rounding: 15,
            },
        };

        registry.category("services").add(
            "lazy_session",
            {
                start() {
                    return {
                        getValue(key, callback) {
                            callback(env.sessionData[key]);
                        },
                    };
                },
            },
            { force: true }
        );

        env.pyEnv = await startServer();

        const spec =
            env.pyEnv["account.analytic.line"]._get_aw_timesheet_fields_specification?.() || {};
        const fieldNames = Object.keys(spec);
        const domain = [["date", "=", luxon.DateTime.now().toFormat("yyyy-MM-dd")]];

        env.sessionData.timesheets_today = {
            records: env.pyEnv["account.analytic.line"].web_search_read(domain, spec).records || [],
        };

        const rawDefaults = env.pyEnv["account.analytic.line"].default_get(fieldNames);
        const timesheetDefaultValues = {};
        for (const field of fieldNames) {
            if (field === "id") {
                continue;
            }
            timesheetDefaultValues[field] =
                rawDefaults[field] !== undefined ? rawDefaults[field] : false;
        }

        env.sessionData.timesheet_default_values = timesheetDefaultValues;
        env.sessionData.timesheet_timer_fields =
            env.pyEnv["account.analytic.line"].fields_get(fieldNames);

        onRpc("/timesheet_grid/timesheet_systray_user_data", async (request) => {
            const spec =
                env.pyEnv["account.analytic.line"]._get_aw_timesheet_fields_specification();
            const domain = [["date", "=", luxon.DateTime.now().toFormat("yyyy-MM-dd")]];
            return {
                employee: { ...env.employeeData },
                timesheets: {
                    records: env.pyEnv["account.analytic.line"].web_search_read(domain, spec)
                        .records,
                },
            };
        });

        onRpc("/timesheet_grid/get_timer_start_time", () => ({
            elapsed_seconds: 0,
        }));

        onRpc("account.analytic.line", "action_round_timesheet_time", ({ args }) => {
            const [recordId] = args;
            const record = env.pyEnv["account.analytic.line"].browse(recordId)[0];
            return (
                roundTimeSpent({
                    minutesSpent: record.unit_amount * 60,
                    ...env.sessionData.timesheet_rounding_values,
                }) / 60
            );
        });
    });

    return env;
}

export async function advanceTimer(ms) {
    if (ms > 1000) {
        await advanceTime(ms - 1000);
        await tick();
    }
    await advanceTime(1000);
    await tick();
}

export function setPreFilledFormTimesheet(record) {
    localStorage.setItem("timesheet.preFilledForm", JSON.stringify(record));
}
