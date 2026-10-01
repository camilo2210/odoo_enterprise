import { registry } from "@web/core/registry";
import { formatFloatTime } from "@web/views/fields/formatters";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, useProps } from "@odoo/owl";

export class TimeConditionHoursField extends Component {
    static template = "voip.TimeConditionHoursField";

    props = useProps(standardFieldProps);

    get displayValue() {
        const { all_day: allDay, hours_start: start, hours_end: end } = this.props.record.data;
        return allDay
            ? this.props.record.data[this.props.name]
            : `${formatFloatTime(start)} → ${formatFloatTime(end)}`;
    }
}

registry.category("fields").add("voip_time_condition_hours", {
    component: TimeConditionHoursField,
    supportedTypes: ["char"],
});
