import { components } from "@odoo/o-spreadsheet";
import { patch } from "@web/core/utils/patch";
import { DateTimePickerPopover } from "@web/core/datetime/datetime_picker_popover";
import { usePopover } from "@web/core/popover/popover_hook";
import { signal, t, useProps } from "@odoo/owl";

const { CalendarButton } = components;
const { DateTime } = luxon;

patch(CalendarButton.prototype, {
    setup() {
        super.setup();
        this.popover = usePopover(DateTimePickerPopover, { position: "bottom-start" });
        this.buttonRef = signal.ref();
        this.spreadsheetEditionProps = useProps({
            value: t.string().optional(),
        });
    },

    openCalendar() {
        const dateValue = this.formatDateForInput(this.spreadsheetEditionProps.value);
        this.popover.open(this.buttonRef(), {
            pickerProps: {
                type: "date",
                onSelect: (date) => {
                    const dateStr = date.toISODate();
                    this.props.onChange(dateStr);
                    this.popover.close();
                },
                value: DateTime.fromISO(dateValue),
            },
        });
    },
});
