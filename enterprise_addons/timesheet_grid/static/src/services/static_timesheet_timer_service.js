import { proxy } from "@odoo/owl";
import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { omit } from "@web/core/utils/objects";
import { getFieldFromRegistry, getPropertyFieldInfo } from "@web/views/fields/field";
import { formatFloatTime } from "@web/views/fields/formatters";
import { roundTimeSpent } from "@timesheet_grid/utils/timer";

const { DateTime } = luxon;
const FIRST_OPEN_KEY = "timesheet_timer_first_open";
const MANUAL_CHANGE_KEY = "timesheet_timer_manual_change";
const ACTIVE_TIMESHEET_KEY = "timesheet_timer_active_id";
const ACTIVE_TIMER_SESSIONS_KEY = "active_timer_sessions";

export const staticTimesheetTimerService = {
    dependencies: ["timer", "lazy_session", "ui"],

    start(env, { timer: timerService, lazy_session: lazySession, ui }) {
        const timer = timerService.createTimer();
        const timerState = proxy({
            startTime: null,
            values: null,
            hasManualEdit: false,
        });

        let roundingValues = { minimum: 0, rounding: 0 };
        lazySession.getValue("timesheet_rounding_values", (values) => {
            if (values) {
                roundingValues = values;
            }
        });

        let timesheetTimerFields = {};
        lazySession.getValue("timesheet_timer_fields", (value) => {
            if (value) {
                timesheetTimerFields = value;
            }
        });

        let initialized = false;

        window.addEventListener("focus", () => {
            // Reload the timer to make sure we are up to date with the user's manual changes in other tabs/windows
            initialized = false;
        });

        function getDisplayString() {
            const h = String(timer.hours).padStart(2, "0");
            const m = String(timer.minutes).padStart(2, "0");
            return `${h}:${m}`;
        }

        function getTodayString() {
            return DateTime.local().toISODate();
        }

        function loadFirstOpenTime() {
            const stored = localStorage.getItem(FIRST_OPEN_KEY);
            if (!stored) {
                return null;
            }
            const data = JSON.parse(stored);
            if (data.date !== getTodayString()) {
                localStorage.removeItem(FIRST_OPEN_KEY);
                return null;
            }
            return data.firstOpenTime;
        }

        function saveFirstOpenTime(isoTime) {
            localStorage.setItem(
                FIRST_OPEN_KEY,
                JSON.stringify({
                    date: getTodayString(),
                    firstOpenTime: isoTime,
                })
            );
        }

        function clearManualChange() {
            localStorage.removeItem(MANUAL_CHANGE_KEY);
            timerState.values = null;
        }

        function loadManualChange() {
            const stored = localStorage.getItem(MANUAL_CHANGE_KEY);
            if (!stored) {
                return null;
            }
            const data = JSON.parse(stored);
            if (data.date !== getTodayString()) {
                clearManualChange();
                return null;
            }
            return {
                changeTime: data.changeTime,
                timerSeconds: data.timerSeconds,
                values: data.values,
                isPaused: data.isPaused || false,
            };
        }

        function loadManualValues() {
            const stored = localStorage.getItem(MANUAL_CHANGE_KEY);
            if (!stored) {
                return null;
            }
            const data = JSON.parse(stored);
            if (data.date !== getTodayString()) {
                clearManualChange();
                return null;
            }
            return data.values;
        }

        function saveManualChange(changeTime, timerSeconds, values, isPaused = false) {
            const data = {
                date: getTodayString(),
                changeTime: changeTime,
                timerSeconds: timerSeconds,
                isPaused: isPaused,
            };
            if (values && Object.keys(values).length > 0) {
                data.values = values;
            }
            localStorage.setItem(MANUAL_CHANGE_KEY, JSON.stringify(data));
            timerState.values = values;
        }

        function saveActiveTimerSessions(action) {
            // Records the physical play/pause intervals of the active timer.
            let sessions = JSON.parse(localStorage.getItem(ACTIVE_TIMER_SESSIONS_KEY) || "[]");
            const now = DateTime.local().toISO();

            if (action === "start") {
                if (sessions.length === 0 || sessions[sessions.length - 1].stop !== null) {
                    sessions.push({ start: now, stop: null });
                }
            } else if (action === "stop") {
                if (sessions.length > 0 && sessions[sessions.length - 1].stop === null) {
                    sessions[sessions.length - 1].stop = now;
                }
            } else if (action === "clear") {
                sessions = [];
            }

            localStorage.setItem(ACTIVE_TIMER_SESSIONS_KEY, JSON.stringify(sessions));
        }

        return {
            ...timerService,

            get timer() {
                return timer;
            },
            get timerState() {
                return timerState;
            },
            get timesheetTimerFields() {
                return timesheetTimerFields;
            },
            set timesheetTimerFields(fields) {
                timesheetTimerFields = fields;
            },

            updateAndGetTime() {
                if (timerState.startTime) {
                    timer.updateTimer(timerState.startTime);
                }
                return getDisplayString();
            },

            getCurrentFloatValue(round = false) {
                if (timerState.startTime) {
                    timer.updateTimer(timerState.startTime);
                    const totalSeconds = timer.hours * 3600 + timer.minutes * 60 + timer.seconds;
                    let totalMinutes = totalSeconds / 60;

                    if (round) {
                        totalMinutes = roundTimeSpent({
                            minutesSpent: totalMinutes,
                            ...roundingValues,
                        });
                    }

                    return totalMinutes / 60;
                }
                return 0.0;
            },

            async initTimer() {
                if (initialized) {
                    return;
                }
                initialized = true;

                const storedId = this.loadActiveTimesheetId();
                if (storedId) {
                    timerState.activeTimesheetId = storedId;
                }

                const currentTime = timer.getCurrentTime();

                let firstOpenTime = loadFirstOpenTime();
                if (!firstOpenTime) {
                    firstOpenTime = currentTime.toISO();
                    saveFirstOpenTime(firstOpenTime);
                }

                const manualChange = loadManualChange();
                let startTime = null;

                if (manualChange && manualChange.changeTime && manualChange.timerSeconds != null) {
                    if (manualChange.isPaused) {
                        timerState.startTime = null;
                        timerState.values = manualChange.values;
                        initialized = true;
                        return;
                    }

                    const changeTime = DateTime.fromISO(manualChange.changeTime);
                    const storedSeconds = Number(manualChange.timerSeconds) || 0;
                    const diffResult = currentTime.diff(changeTime, ["seconds"]);
                    const elapsedSinceChange = diffResult.seconds || 0;
                    const totalSeconds = Math.floor(
                        storedSeconds + Math.max(0, elapsedSinceChange)
                    );
                    startTime = currentTime.minus({ seconds: totalSeconds });
                    timerState.values = manualChange.values;
                } else {
                    const data = await rpc("/timesheet_grid/get_timer_start_time");
                    if (data.elapsed_seconds) {
                        startTime = currentTime.minus({ seconds: data.elapsed_seconds });
                    } else {
                        startTime = DateTime.fromISO(firstOpenTime);
                    }
                }

                if (startTime) {
                    timerState.startTime = startTime;
                    timer.updateTimer(timerState.startTime);
                    saveActiveTimerSessions("start");
                }
            },

            pauseTimer() {
                if (!timerState.startTime) {
                    return;
                }
                timer.updateTimer(timerState.startTime);
                const existingValues = loadManualValues() || {};

                saveManualChange(
                    timer.getCurrentTime().toISO(),
                    timer.toSeconds,
                    existingValues,
                    true
                );
                timerState.startTime = null;
                saveActiveTimerSessions("stop");
            },

            resumeTimer(overrideSeconds = null) {
                const manualChange = loadManualChange();
                if (manualChange && manualChange.isPaused) {
                    const storedSeconds =
                        overrideSeconds !== null
                            ? overrideSeconds
                            : Number(manualChange.timerSeconds) || 0;

                    timerState.startTime = timer.getCurrentTime().minus({ seconds: storedSeconds });
                    timer.updateTimer(timerState.startTime);

                    saveManualChange(
                        timer.getCurrentTime().toISO(),
                        storedSeconds,
                        manualChange.values,
                        false
                    );
                    saveActiveTimerSessions("start");
                }
            },

            setManualValue(hours, minutes, seconds = 0, save = true, values = null) {
                const currentTime = timer.getCurrentTime();
                timerState.startTime = currentTime.minus({ hours, minutes, seconds });
                timer.updateTimer(timerState.startTime);

                if (save) {
                    if (!values) {
                        const existing = loadManualChange();
                        values = existing?.values || null;
                    }
                    saveManualChange(currentTime.toISO(), timer.toSeconds, values);
                }
            },

            setFromFloat(floatValue) {
                const timeString = formatFloatTime(floatValue, {
                    numeric: true,
                    showSeconds: true,
                });
                const [hours, minutes, seconds] = timeString.split(":").map(Number);
                this.setManualValue(hours, minutes, seconds, false);
            },

            resetTimer() {
                this.setManualValue(0, 0, 0, true, {});
                this.clearActiveTimesheetId();
                timerState.hasManualEdit = false;
                saveActiveTimerSessions("clear");
                saveActiveTimerSessions("start");
            },

            setStartTimeFromTimesheet(timesheet) {
                if (!timesheet?.create_date) {
                    return;
                }

                const start = DateTime.fromISO(timesheet.create_date);
                timerState.startTime = start;

                const now = this.timer.getCurrentTime();
                timer.setTimer(0, start, now);
                timer.formatTime();
                clearManualChange();
                saveActiveTimerSessions("start");
            },

            getTimesheetTimerFieldInfo(fieldName, fields = {}) {
                const field = fields[fieldName] || timesheetTimerFields[fieldName];
                if (!field) {
                    return {};
                }
                const propertyField = {
                    ...field,
                    domain: field.domain || "[]",
                    required: "False",
                };
                const fieldInfo = getPropertyFieldInfo(propertyField);
                if (fieldName === "task_id") {
                    fieldInfo.field = getFieldFromRegistry(propertyField.type, "task_with_hours");
                } else if (fieldName === "unit_amount" && !propertyField.widget) {
                    fieldInfo.field = getFieldFromRegistry(fieldInfo.type, "timesheet_uom");
                } else if (fieldName === "name") {
                    if (!fieldInfo.options) {
                        fieldInfo.options = {};
                    }
                    fieldInfo.options.line_breaks = false;
                    fieldInfo.field = getFieldFromRegistry(fieldInfo.type, "text");
                }
                fieldInfo.placeholder = ui.isSmall ? "" : field.string || "";
                if (fieldName === "project_id") {
                    fieldInfo.domain = Domain.and([
                        fieldInfo.domain,
                        new Domain([["allow_timesheets", "=", true]]),
                    ]).toString();
                    fieldInfo.context = `{'search_default_my_projects': True, 'timesheet_timer_search': True}`;
                    fieldInfo.required = "True";
                } else if (fieldName === "task_id") {
                    fieldInfo.context = `{'default_project_id': project_id, 'search_default_my_tasks': True, 'search_default_open_tasks': True, 'hide_timesheet_ids': True, 'timesheet_timer_search': True}`;
                } else if (fieldName === "name") {
                    fieldInfo.placeholder = ui.isSmall ? "" : _t("What did you work on?");
                }
                if (field.depends?.length) {
                    fieldInfo.onChange = true;
                }
                return fieldInfo;
            },

            loadActiveTimesheetId() {
                const stored = localStorage.getItem(ACTIVE_TIMESHEET_KEY);
                return stored ? parseInt(stored, 10) : null;
            },

            startNewTimesheet(timesheet) {
                const currentTime = timer.getCurrentTime();
                const ignoredFields = ["id", "unit_amount", "name", "date"];
                const copyParams = omit(timesheet, ...ignoredFields);
                timerState.startTime = currentTime;
                timer.updateTimer(currentTime);

                saveManualChange(
                    currentTime.toISO(),
                    0,
                    copyParams
                );

                this.clearActiveTimesheetId();

                saveActiveTimerSessions("clear");
                saveActiveTimerSessions("start");
            },

            saveActiveTimesheetId(id) {
                if (id) {
                    localStorage.setItem(ACTIVE_TIMESHEET_KEY, id);
                    timerState.activeTimesheetId = id;
                }
            },

            clearActiveTimesheetId() {
                localStorage.removeItem(ACTIVE_TIMESHEET_KEY);
                timerState.activeTimesheetId = null;
            },

            saveManualChange,
            clearManualChange,
            loadManualValues,
        };
    },
};

registry.category("services").add("static_timesheet_timer", staticTimesheetTimerService);
