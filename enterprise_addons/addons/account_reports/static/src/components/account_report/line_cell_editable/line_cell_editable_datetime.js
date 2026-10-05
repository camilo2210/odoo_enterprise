import { formatDate, formatDateTime } from "@web/core/l10n/dates";

import { useDateTimePicker } from "@web/core/datetime/datetime_picker_hook";

import { Component, computed, signal, t, usePlugin, useProps } from "@odoo/owl";

import { AccountReportController } from "@account_reports/components/account_report/controller";

const { DateTime } = luxon;


export class AccountReportLineCellEditableDateTime extends Component {
    static template = "account_reports.AccountReportLineCellEditableDateTime";
    props = useProps({
        onChange: t.function(),
        cell: t.object(),
        audit: t.function(),
    });

    controller = usePlugin(AccountReportController);
    
    datetime = computed(
        () => this.props.cell.no_format() ? DateTime.fromISO(this.props.cell.no_format()) : null,
        {set: this.props.cell.no_format.set},
    );

    inputDateRef = signal.ref();

    setup() {
        this.datetimePicker = useDateTimePicker({
            target: this.inputDateRef,
            showSeconds: false,
            tz: this.tz,
            pickerProps: this.pickerProps,
            onApply: newDate => {
                this.datetime.set(newDate);
                this.props.onChange(newDate);
            },
        });
    }

    get pickerProps() {
        return {
            value: this.datetime(),
            type: this.figureType,
        };
    }

    onClickEdit() {
        this.datetimePicker.open();
    }

    onBlur() {
        this.datetimePicker.close();
    }

    onMouseDown(ev) {
        /**
         * This function has for purpose to prevent the input focus via the click without
         * blocking the click when the element is focus.
         */
        if (!this.datetimePicker.isOpen()) {
            ev.preventDefault();
        }
    }

    audit() {
        if (this.datetimePicker.isOpen()) {
            return;
        }
        this.props.audit();
    }

    get tz() {
        return this.controller.context?.tz || "UTC";
    }

    get inputValue() {
        const value = this.datetime();
        if (value) {
            if (this.figureType === "datetime") {
                return formatDateTime(value, { tz: this.tz });
            } else if (this.figureType === "date") {
                return formatDate(value, { tz: this.tz });
            } else {
                throw new Error(
                    `Bad figure type to format. Expected: date, datetime. Got: ${this.figureType}`
                );
            }
        }
        return "";
    }

    get figureType() {
        return this.props.cell.figure_type();
    }
}
