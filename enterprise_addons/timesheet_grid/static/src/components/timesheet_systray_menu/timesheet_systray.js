import { useSubEnv } from "@web/owl2/utils";
import { Component, onWillStart, proxy, t, useOnChange, useListener, useProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { formatDurationTimesheet } from "@timesheet_grid/utils/timer";
import { TimesheetTimerInlineForm } from "@timesheet_grid/components/timesheet_timer_inline_form/timesheet_timer_inline_form";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { useCommand } from "@web/core/commands/command_hook";
import { _t } from "@web/core/l10n/translation";
import { browser } from "@web/core/browser/browser";

const { DateTime } = luxon;

export class TimesheetSystrayContent extends Component {
    static components = { TimesheetTimerInlineForm };
    static template = "timesheet_grid.TimesheetSystrayContent";

    props = useProps({
        closeDropdown: t.function().optional(),
        checkInData: t.object().optional(),
        signInOut: t.function(),
    });

    formatDuration = formatDurationTimesheet;

    get totalTime() {
        return this.cacheState.timesheets.reduce((sum, ts) => sum + ts.unit_amount, 0);
    }

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.staticTimerService = useService("static_timesheet_timer");
        this.cache = useService("timesheet_systray_cache");
        this.cacheState = this.cache.state;
        this.menu = useService("menu");
        this.lazySession = useService("lazy_session");
        this.employee = false;

        this.state = proxy({
            selectedTimesheet: {},
            showAssistant: false,
        });

        onWillStart(async () => {
            this.staticTimerService.initTimer();
            this.cache.fetchPreFilledForm();
            this.lazySession.getValue("display_timesheets_assistant", (value) => {
                this.state.showAssistant = value;
            });
            this.lazySession.getValue("timesheet_systray_employee_data", (value) => {
                this.employee = value;
            });

            this.restoreActiveTimesheet();
            this.cache.fetchTimesheets();
        });

        // if the dropdown opened before the cache was ready, restore once it loads
        let wasLoaded = this.cacheState.loaded;
        useOnChange(
            () => [this.cacheState.loaded],
            (loaded) => {
                if (loaded && !wasLoaded) {
                    this.restoreActiveTimesheet();
                }
                wasLoaded = loaded;
            }
        );

        // Close dropdown when following an internal link
        useSubEnv({
            services: {
                ...this.env.services,
                action: {
                    ...this.action,
                    doAction: (actionRequest, options) => {
                        this.props.closeDropdown?.();
                        return this.action.doAction(actionRequest, options);
                    },
                },
            },
        });
        // Close dropdown when switching tab/window to ensure the saved data is up to date
        useListener(window, "blur", () => {
            this.props.closeDropdown?.();
        });
    }

    restoreActiveTimesheet() {
        const activeId = this.staticTimerService.timerState.activeTimesheetId;
        if (activeId) {
            const record = this.cacheState.timesheets.find((ts) => ts.id === activeId);
            if (record) {
                this.onClickTimesheet(record);

                const savedValues = this.staticTimerService.loadManualValues();
                if (savedValues) {
                    Object.assign(this.state.selectedTimesheet, savedValues);
                }
            } else if (this.cacheState.loaded) {
                this.staticTimerService.clearActiveTimesheetId();
            }
        }
    }

    onClickTimesheet(timesheet) {
        const isNewSelection =
            this.staticTimerService.timerState.activeTimesheetId !== timesheet.id;

        this.state.selectedTimesheet = { ...timesheet };

        if (isNewSelection) {
            this.staticTimerService.saveActiveTimesheetId(timesheet.id);
            this.staticTimerService.timerState.startTime = null;
            this.staticTimerService.clearManualChange();
        }
    }

    async onClickCopy(timesheet) {
        if (this.currentRecord.data?.project_id) {
            if (this.currentRecord.data?.id) {
                await this.currentRecord.update(
                    { unit_amount: this.staticTimerService.getCurrentFloatValue(true) },
                    { save: false }
                );
                await this.currentRecord.save();
                const timesheetData = this.currentRecord.data;
                const timesheet = {
                    ...this.currentRecord,
                    data: timesheetData,
                };
                this.currentRecord = null;
                this.onWriteTimesheet(timesheet);
            } else {
                await this.currentRecord.save();
                const timeSpent = await this.orm.call(
                    this.currentRecord.resModel,
                    "action_round_timesheet_time",
                    [this.currentRecord.data.id]
                );
                await this.currentRecord.update({ unit_amount: timeSpent });
                await this.onSaveTimesheetForm(
                    {
                        ...this.currentRecord,
                        data: this.currentRecord.data,
                    },
                    this.currentRecord.data
                );
            }
        }

        this.staticTimerService.startNewTimesheet(timesheet);
        this.state.selectedTimesheet = {};
    }

    async openAssistantAction() {
        // Open the timesheets app first
        const [, menuId] = await this.orm.call("ir.model.data", "check_object_reference", [
            "hr_timesheet",
            "timesheet_menu_root",
        ]);
        if (menuId) {
            this.menu.setCurrentMenu(menuId);
        }

        this.action.doAction({
            type: "ir.actions.client",
            tag: "hr_timesheet_activitywatch_action",
        });
        this.props.closeDropdown?.();
    }

    onSaveTimesheetForm(timesheet) {
        this.cacheState.pre_filled_form = {};
        this.staticTimerService.clearActiveTimesheetId();
        this.staticTimerService.clearManualChange();
        this.cache.addTimesheet(timesheet.data);
    }

    onWriteTimesheet(timesheet) {
        this.state.selectedTimesheet = {};
        this.staticTimerService.clearActiveTimesheetId();
        this.cache.updateTimesheet(timesheet.data);
    }

    onDeleteTimesheet(timesheetId) {
        this.cache.removeTimesheet(timesheetId);
        this.state.selectedTimesheet = {};
        this.staticTimerService.clearActiveTimesheetId();
    }

    onDiscard() {
        this.cache.clearPreFilledForm();
        this.state.selectedTimesheet = {};
        this.staticTimerService.clearActiveTimesheetId();
        this.staticTimerService.clearManualChange();
    }

    async onRecordReady(record) {
        this.currentRecord = record;
    }

    /**
     * Context with default values for creating new timesheets.
     * When a task/ticket was visited (and there's no draft to restore), its
     * id is passed as a default_ so the record resolves it itself (and
     * everything derived from it) through a real onchange.
     */
    get context() {
        // When editing an existing timesheet, no context needed (data comes from props.data)
        if (this.state.selectedTimesheet?.id) {
            return {};
        }
        const context = {
            default_date: luxon.DateTime.now().toISODate(),
        };
        const prefilledFormValues = this.cacheState.pre_filled_form || {};
        if (
            !this.staticTimerService.loadManualValues() &&
            Object.keys(prefilledFormValues).length > 0
        ) {
            const [fieldName, resId] = Object.entries(prefilledFormValues)[0];
            context[`default_${fieldName}`] = resId;
            // Since values won't be given to the record in this case (see
            // savedTimesheetData), the elapsed time has to be passed here too.
            context.default_unit_amount = this.staticTimerService.getCurrentFloatValue(false);
        }
        return context;
    }

    /**
     * If no timesheet is selected but there are saved manual values, return
     * them as a data object (like selectedTimesheet) so the form is
     * pre-filled without using default_ context. When a draft doesn't exist
     * but a task/ticket pointer is known, return undefined instead so the
     * record resolves it itself (see context).
     */
    get savedTimesheetData() {
        if (this.state.selectedTimesheet?.id) {
            return {};
        }
        const result = this.staticTimerService.loadManualValues();
        if (result) {
            return result;
        }
        if (Object.keys(this.cacheState.pre_filled_form || {}).length > 0) {
            return undefined;
        }
        return {};
    }

    onFormKeydown(ev) {
        // Prevent Tab keydown events from propagating up to the Dropdown and be intercepted by it
        if (["Tab"].includes(ev.key)) {
            ev.stopPropagation();
        }
    }
}

export class TimesheetSystray extends Component {
    static components = { Dropdown, TimesheetSystrayContent };
    static template = "timesheet_grid.timesheet_systray";

    setup() {
        this.lazySession = useService("lazy_session");
        this.staticTimerService = useService("static_timesheet_timer");
        this.state = proxy({
            isDisplayed: false,
            checkInData: this.defaultCheckInData,
        });
        this._loadCheckInData();
        this.dropdownState = useDropdownState();

        useCommand(
            _t("Open Timesheets Systray"),
            () => {
                this.dropdownState.open();
            },
            {
                category: "activity",
                hotkey: "alt+shift+r",
                isAvailable: () => this.state.isDisplayed,
            }
        );

        onWillStart(async () => {
            if (this.state.checkedIn) {
                this.staticTimerService.resumeTimer();
            } else {
                this.staticTimerService.pauseTimer();
            }

            this.lazySession.getValue("display_timesheets_systray", (value) => {
                this.state.isDisplayed = value;
            });
        });
    }

    get defaultCheckInData() {
        return {
            checkedIn: false,
            sessions: [],
            total: { h: 0, m: 0 },
        };
    }
    signInOut() {
        this.state.checkInData.checkedIn = !this.state.checkInData.checkedIn;
        if (this.state.checkInData.checkedIn) {
            this.state.checkInData.sessions.push({
                id: this.state.checkInData.sessions.length,
                startTime: {
                    sign: this.staticTimerService.timer.getCurrentTime().hour >= 12 ? "PM" : "AM",
                    h: this.staticTimerService.timer.getCurrentTime().hour,
                    m: this.staticTimerService.timer.getCurrentTime().minute,
                    s: this.staticTimerService.timer.getCurrentTime().seconds,
                },
                duration: -1,
                endTime: "",
            });
            this.staticTimerService.resumeTimer();
            this._saveCheckInData(this.state.checkInData, user);
            return;
        }

        this.staticTimerService.pauseTimer();
        const lastIndex = this.state.checkInData.sessions.length - 1;
        const startTimeDate = DateTime.now().set({
            hour: this.state.checkInData.sessions[lastIndex].startTime.h,
            minute: this.state.checkInData.sessions[lastIndex].startTime.m,
        });
        const duration = this.staticTimerService.timer
            .getInterval(startTimeDate, this.staticTimerService.timer.getCurrentTime())
            .toDuration(["hours", "minutes"]);

        this.state.checkInData.sessions[lastIndex].duration = {
            h: duration.hours,
            m: Math.floor(duration.minutes),
        };
        this.state.checkInData.sessions[lastIndex].endTime = {
            sign: this.staticTimerService.timer.getCurrentTime().hour >= 12 ? "PM" : "AM",
            h:
                (this.staticTimerService.timer.getCurrentTime().hour % 13) +
                Math.floor(this.staticTimerService.timer.getCurrentTime().hour / 13),
            m: this.staticTimerService.timer.getCurrentTime().minute,
        };
        this.state.checkInData.sessions[lastIndex].startTime.h =
            (this.state.checkInData.sessions[lastIndex].startTime.h % 13) +
            Math.floor(this.state.checkInData.sessions[lastIndex].startTime.h / 13);

        this.state.checkInData.total.h +=
            duration.hours + Math.floor((this.state.checkInData.total.m + duration.minutes) / 60);
        this.state.checkInData.total.m = (this.state.checkInData.total.m + duration.minutes) % 60;

        this._saveCheckInData(this.state.checkInData, user);
    }
    _saveCheckInData(newData, user_id) {
        const oldData = browser.localStorage.getItem("timesheet_checkInData")
            ? JSON.parse(browser.localStorage.getItem("timesheet_checkInData"))
            : null;
        const useExistingData =
            oldData &&
            DateTime.fromISO(oldData.timestamp).toFormat("yyyy MMM dd") ==
                this.staticTimerService.timer.getCurrentTime().toFormat("yyyy MMM dd");
        if (!useExistingData) {
            const saveData = {
                timestamp: this.staticTimerService.timer.getCurrentTime(),
                [user_id.userId]: newData,
            };
            browser.localStorage.setItem("timesheet_checkInData", JSON.stringify(saveData));
            return;
        }

        oldData[user_id.userId] = newData;
        browser.localStorage.setItem("timesheet_checkInData", JSON.stringify(oldData));
    }
    _loadCheckInData() {
        if (!browser.localStorage.getItem("timesheet_checkInData")) {
            return;
        }

        const data = JSON.parse(browser.localStorage.getItem("timesheet_checkInData"));
        data.timestamp = DateTime.fromISO(data.timestamp);
        const currentDate = this.staticTimerService.timer.getCurrentTime();
        if (data.timestamp.toFormat("yyyy MMM dd") != currentDate.toFormat("yyyy MMM dd")) {
            return;
        }

        if (user.userId in data) {
            this.state.checkInData = data[user.userId];
        }
    }
}

export const timesheetSystray = {
    Component: TimesheetSystray,
};

registry
    .category("systray")
    .add("timesheet_grid.timesheet_systray", timesheetSystray, { sequence: 70 });
