import {
    plannedDateRangeWithAllocatedHours,
    PlannedDateRangeWithAllocatedHours,
} from "@planning/components/planned_date_range_with_allocated_hours/planned_date_range_with_allocated_hours";
import { patch } from "@web/core/utils/patch";
import { formatFloatTime } from "@web/views/fields/formatters";
import { _t } from "@web/core/l10n/translation";

patch(PlannedDateRangeWithAllocatedHours.prototype, {
    get allocatedHoursFormatted() {
        const allocatedHoursFormatted = super.allocatedHoursFormatted;
        if (this.props.record.data.allocated_hours && this.props.record.data.break_time) {
            const breakTimeFormatted = formatFloatTime(this.props.record.data.break_time);
            return _t("%(allocatedHoursFormatted)s + %(breakTimeFormatted)s break", {
                allocatedHoursFormatted,
                breakTimeFormatted,
            });
        }
        return allocatedHoursFormatted;
    },
});

patch(plannedDateRangeWithAllocatedHours, {
    fieldDependencies: [
        ...plannedDateRangeWithAllocatedHours.fieldDependencies,
        {
            name: "break_time",
            type: "float",
        },
    ],
});
