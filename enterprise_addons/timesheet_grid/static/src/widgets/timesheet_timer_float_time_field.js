import { onPatched, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { FloatTimeField, floatTimeField } from "@web/views/fields/float_time/float_time_field";
import { formatFloatTime } from "@web/views/fields/formatters";
import { registry } from "@web/core/registry";

export class TimesheetTimerFloatTimeField extends FloatTimeField {
    setup() {
        super.setup();
        this.staticTimerService = useService("static_timesheet_timer");
        this.state.isFocused = false;
        let previousFocusState = this.state.isFocused;

        onPatched(() => {
            if (previousFocusState !== this.state.isFocused) {
                previousFocusState = this.state.isFocused;
                if (this.state.isFocused && this.inputFloatTimeRef()) {
                    this.inputFloatTimeRef().select();
                }
            }
        });

        // Ticks locally so only this widget re-renders every second, instead
        // of the record (and the whole inline form) being patched each tick.
        let tickInterval = null;
        onWillStart(() => {
            tickInterval = setInterval(() => {
                if (this.isTimerTicking) {
                    this.staticTimerService.updateAndGetTime();
                }
            }, 1000);
        });
        onWillUnmount(() => clearInterval(tickInterval));
    }

    get isTimerTicking() {
        return Boolean(this.staticTimerService.timerState.startTime) && !this.state.isFocused;
    }

    get formatOptions() {
        const options = super.formatOptions;
        if (this.state.isFocused) {
            options.showSeconds = false;
        }
        return options;
    }

    get formattedValue() {
        if (this.isTimerTicking) {
            return formatFloatTime(
                this.staticTimerService.getCurrentFloatValue(false),
                this.formatOptions
            );
        }
        return super.formattedValue;
    }

    openPopover() {
        this.state.isFocused = true;
        this.valueAtFocus = this.props.record.data[this.props.name];
        this.staticTimerService.pauseTimer();
        super.openPopover();
    }

    closePopover() {
        this.state.isFocused = false;
        // Compare against the record's own committed value: it can only change here
        // through this same field's input, so a mismatch means the user typed one.
        const editedValue = this.props.record.data[this.props.name];
        const wasEdited = this.valueAtFocus !== undefined && editedValue !== this.valueAtFocus;
        if (wasEdited) {
            this.staticTimerService.timerState.hasManualEdit = true;
            // Resume from the value the user just typed, not the value that was
            // running before they focused in, so the count keeps going from there.
            this.staticTimerService.resumeTimer(Math.round(editedValue * 3600));
        } else {
            this.staticTimerService.resumeTimer();
        }
        super.closePopover();
    }
}

export const timesheetTimerFloatTimeField = {
    ...floatTimeField,
    component: TimesheetTimerFloatTimeField,
};

registry.category("fields").add("timesheet_timer_float_time", timesheetTimerFloatTimeField);
