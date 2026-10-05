import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { proxy } from "@odoo/owl";

export const timesheetSystrayCacheService = {
    dependencies: ["lazy_session"],

    start(env, { lazy_session: lazySession }) {
        let fetchPromise = null;

        const state = proxy({
            timesheets: [],
            pre_filled_form: {},
            loaded: false,
        });

        lazySession.getValue("timesheets_today", (value) => {
            if (value) {
                state.timesheets = value.records;
            }
            state.loaded = true;
        });

        return {
            get state() {
                return state;
            },

            async fetchTimesheets() {
                if (fetchPromise) {
                    return fetchPromise;
                }

                fetchPromise = (async () => {
                    try {
                        const data = await rpc("/timesheet_grid/timesheet_systray_user_data");
                        const newRecords = data.timesheets?.records || [];

                        if (JSON.stringify(state.timesheets) !== JSON.stringify(newRecords)) {
                            state.timesheets = newRecords;
                        }
                        state.loaded = true;
                    } finally {
                        fetchPromise = null;
                    }
                })();

                return fetchPromise;
            },

            fetchPreFilledForm() {
                state.pre_filled_form = JSON.parse(
                    localStorage.getItem("timesheet.preFilledForm") || "{}"
                );
                return state.pre_filled_form;
            },

            clearPreFilledForm() {
                localStorage.removeItem("timesheet.preFilledForm");
                state.pre_filled_form = {};
            },

            addTimesheet(timesheet) {
                state.timesheets.unshift(timesheet);
            },

            updateTimesheet(timesheet) {
                const index = state.timesheets.findIndex((ts) => ts.id === timesheet.id);
                if (index !== -1) {
                    state.timesheets[index] = timesheet;
                }
            },

            removeTimesheet(timesheetId) {
                state.timesheets = state.timesheets.filter((ts) => ts.id !== timesheetId);
            },
        };
    },
};

registry.category("services").add("timesheet_systray_cache", timesheetSystrayCacheService);
