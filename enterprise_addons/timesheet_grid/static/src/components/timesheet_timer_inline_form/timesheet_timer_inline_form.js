import { onWillUnmount, untrack } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { TimesheetInlineForm } from "../timesheet_inline_form/timesheet_inline_form";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class TimesheetTimerInlineForm extends TimesheetInlineForm {
    static template = "timesheet_grid.TimesheetTimerInlineForm";

    setup() {
        super.setup();
        this.lazySession = useService("lazy_session");

        this.defaultValues = {};

        this.lazySession.getValue("timesheet_default_values", (value) => {
            this.defaultValues = value;
        });

        onWillUnmount(() => {
            this.saveManualValuesOnUnmount();
        });
    }

    async onWillStart() {
        await super.onWillStart();
        if (this.props.data?.unit_amount !== undefined) {
            const currentActiveId = this.staticTimerService.timerState.activeTimesheetId;
            const thisRecordId = this.props.data.id;
            if (
                thisRecordId &&
                currentActiveId === thisRecordId &&
                !!this.staticTimerService.timerState.startTime
            ) {
                return;
            }
            this.staticTimerService.setFromFloat(this.props.data.unit_amount);
        }
    }

    storeAssistantBlockouts(timesheetId) {
        if (!timesheetId) {
            return;
        }
        const sessionsStr = localStorage.getItem("active_timer_sessions");
        if (!sessionsStr) {
            return;
        }
        const sessions = JSON.parse(sessionsStr);
        if (sessions.length === 0) {
            return;
        }
        if (sessions[sessions.length - 1].stop === null) {
            sessions[sessions.length - 1].stop = luxon.DateTime.local().toISO();
        }
        const cacheStr = localStorage.getItem("timesheet_assistant_blockouts") || "{}";
        const cache = JSON.parse(cacheStr);
        const todayStr = luxon.DateTime.local().toISODate();
        if (!cache[todayStr]) {
            cache[todayStr] = {};
        }
        if (!cache[todayStr][timesheetId]) {
            cache[todayStr][timesheetId] = [];
        }
        const minifiedSessions = sessions.map((s) => [s.start, s.stop]);
        cache[todayStr][timesheetId].push(...minifiedSessions);
        localStorage.setItem("timesheet_assistant_blockouts", JSON.stringify(cache));
    }

    async onSave(record) {
        const isValid = await record.checkValidity({ displayNotification: true });
        if (isValid) {
            // Only sync the live ticking value when there was no manual edit.
            // Once the user has typed a value, it keeps ticking on screen for
            // feedback, but the saved amount must stay exactly what they typed,
            // not that value plus however long it took them to hit Save.
            if (!this.staticTimerService.timerState.hasManualEdit) {
                await record.update(
                    { unit_amount: this.staticTimerService.getCurrentFloatValue(false) },
                    { save: false }
                );
            }
            await super.onSave(record);
            if (record.resId) {
                this.storeAssistantBlockouts(record.resId);
            }
            this.staticTimerService.resetTimer();
        }
        return isValid;
    }

    async _saveTimesheet(record) {
        const timesheetData = await super._saveTimesheet(record);
        if (timesheetData && !this.staticTimerService.timerState.hasManualEdit) {
            const timeSpent = await this.orm.call(record.resModel, "action_round_timesheet_time", [
                record.resId,
            ]);
            return {
                ...timesheetData,
                unit_amount: timeSpent,
            };
        }
        return timesheetData;
    }

    async onDiscard(record) {
        await super.onDiscard(record);
        this.currentRecord = record;
        this.staticTimerService.resetTimer();
    }

    async onDelete(record) {
        const isDeleted = await super.onDelete(record);
        if (isDeleted) {
            this.staticTimerService.resetTimer();
        }
        return isDeleted;
    }

    getManualValues(record) {
        const values = {};
        for (const [key, value] of Object.entries(record.data)) {
            // Fields blacklist
            if (["id", "date", "unit_amount", "user_id", "company_id"].includes(key)) {
                continue;
            }
            if (Array.isArray(value)) {
                values[key] = value;
            } else if (value && typeof value === "object") {
                if ("id" in value) {
                    values[key] = [value.id, value.display_name || ""];
                }
            } else if (value) {
                values[key] = value;
            }
        }
        return values;
    }

    saveManualValuesOnUnmount() {
        // Only what the user actually typed is worth keeping: an untouched form
        // saved as a draft would shadow the prefill of the next task they visit.
        if (
            !this.currentRecord ||
            !this.isFormEdited(this.currentRecord) ||
            this.staticTimerService.timerState.startTime === null
        ) {
            return;
        }
        const values = this.getManualValues(this.currentRecord);
        const t = this.staticTimerService.timer;
        this.staticTimerService.saveManualChange(t.getCurrentTime().toISO(), t.toSeconds, values);
    }

    get isNewRecord() {
        return !this.props.data?.id;
    }

    get discardButtonText() {
        return this.isNewRecord ? _t("Reset") : _t("Discard");
    }

    get activeFields() {
        // We cache the fields to avoid refetching them every second because of the timer
        if (!this._cachedActiveFields) {
            const fields = super.activeFields;

            fields.project_id.placeholder = fields.project_id.string;
            fields.task_id.placeholder = fields.task_id.string;

            if (fields.unit_amount) {
                const timesheetTimerFloatTimeWidget = registry
                    .category("fields")
                    .get("timesheet_timer_float_time");

                fields.unit_amount = {
                    ...fields.unit_amount,
                    field: timesheetTimerFloatTimeWidget,
                    options: {
                        ...(fields.unit_amount.options || {}),
                        show_seconds: true,
                    },
                };
            }

            this._cachedActiveFields = fields;
        }

        return this._cachedActiveFields;
    }

    get recordData() {
        if (super.recordData === undefined) {
            return undefined;
        }
        // untrack: this is only ever consumed once, to seed a new record's initial
        // values. Reading it live (untracked) would otherwise subscribe this whole
        // form to the same ticking timer state the widget re-renders on every second.
        return {
            ...this.defaultValues,
            ...super.recordData,
            unit_amount: untrack(() => this.staticTimerService.getCurrentFloatValue(false)),
        };
    }
}
