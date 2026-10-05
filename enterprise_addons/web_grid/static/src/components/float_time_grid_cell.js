import { computed } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatFloatTime } from "@web/views/fields/formatters";
import { parseFloatTime } from "@web/views/fields/parsers";
import { GridCell } from "./grid_cell";

export class FloatTimeGridCell extends GridCell {
    inputMode = "text";

    formattedValue = computed(() => formatFloatTime(this.value()));

    parse(value) {
        return parseFloatTime(value);
    }
}

export const floatTimeGridCell = {
    component: FloatTimeGridCell,
    formatter: formatFloatTime,
};

registry.category("grid_components").add("float_time", floatTimeGridCell);
