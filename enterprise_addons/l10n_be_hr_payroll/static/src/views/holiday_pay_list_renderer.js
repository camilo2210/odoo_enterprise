import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";

export class HolidayPayListRenderer extends ListRenderer {

    getCellClass(column, record) {
        let classes = super.getCellClass(column, record);

        if (column.name === "already_allocated_paid_time_off") {
            const allocatedValue = record.data.already_allocated_paid_time_off || 0;
            if (allocatedValue !== 0) {
                classes += " bg-warning-subtle text-warning-emphasis fw-bold";
            }
        }

        if (column.name === "paid_time_off_to_allocate") {
            const toAllocateValue = record.data.paid_time_off_to_allocate || 0;
            if (toAllocateValue === 0) {
                classes += " bg-info-subtle text-info-emphasis fw-bold";
            }
        }

        return classes;
    }
}

export class HolidayPayListX2ManyField extends X2ManyField {}
HolidayPayListX2ManyField.components = {
    ...X2ManyField.components,
    ListRenderer: HolidayPayListRenderer,
};

registry.category("fields").add("holiday_pay_list_widget", {
    ...x2ManyField,
    component: HolidayPayListX2ManyField,
});
