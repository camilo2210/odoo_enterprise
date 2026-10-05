import { computed, t, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatFloatFactor } from "@web/views/fields/formatters";
import { standardGridCellProps } from "../hooks/grid_cell_hook";
import { GridCell } from "./grid_cell";

export class FloatFactorGridCell extends GridCell {
    props = useProps({
        ...standardGridCellProps,
        digits: t.array().optional(),
        factor: t.number().optional(),
        readonly: t.boolean().optional(false),
        trailingZeros: t.boolean().optional(true),
    });

    factor = computed(() => this.props.factor || this.props.fieldInfo.options?.factor || 1);
    formattedValue = computed(() =>
        formatFloatFactor(this.value(), {
            trailingZeros: this.props.trailingZeros,
        })
    );

    getCellValue() {
        return super.getCellValue() * this.factor();
    }

    parse(value) {
        const factorValue = value / this.factor();
        return super.parse(factorValue.toString());
    }
}

export const floatFactorGridCell = {
    component: FloatFactorGridCell,
    formatter: formatFloatFactor,
};

registry.category("grid_components").add("float_factor", floatFactorGridCell);
