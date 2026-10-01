import { Component, computed, signal, t, useEffect, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatFloatFactor } from "@web/views/fields/formatters";
import { standardGridCellProps, useGridCell } from "@web_grid/hooks/grid_cell_hook";
import { GridCell } from "../views/grid_model";

export class FloatToggleGridCell extends Component {
    static template = "web_grid.FloatToggleGridCell";

    props = useProps({
        ...standardGridCellProps,
        digits: t.array().optional(),
        factor: t.number().optional(),
        readonly: t.boolean().optional(false),
        trailingZeros: t.boolean().optional(true),
    });

    invalid = signal(false);
    cell = signal(null, { type: t.instanceOf(GridCell) });
    buttonRef = signal.ref(HTMLButtonElement);

    factor = computed(() => this.props.factor || this.props.fieldInfo.options?.factor || 1);
    formattedValue = computed(() =>
        formatFloatFactor(this.cell()?.value || 0, {
            digits: this.props.fieldInfo.attrs?.digits || 2,
            factor: this.factor(),
            trailingZeros: this.props.trailingZeros,
        })
    );
    isEditable = computed(() => {
        const cell = this.cell();
        return !this.props.readonly && cell?.readonly === false && !cell.row.isSection;
    });
    range = computed(() => this.props.fieldInfo.options?.range || [0.0, 0.5, 1.0]);
    value = computed(() => (this.cell().value || 0) * this.factor());

    gridCellHook = useGridCell(this.cell, this.isEditable);

    setup() {
        useEffect(() => this.buttonRef()?.focus());
    }

    onChange() {
        const range = this.range();
        let currentIndex = range.indexOf(this.value());
        currentIndex++;
        if (currentIndex > range.length - 1) {
            currentIndex = 0;
        }
        this.update(range[currentIndex] / this.factor());
    }

    update(value) {
        this.cell().update(value);
    }

    onCellClick(ev) {
        if (this.isEditable() && !this.props.editMode && !ev.target.closest(".o_grid_search_btn")) {
            this.onChange();
            this.props.onEdit(true);
        }
    }

    onKeyDown(ev) {
        this.props.onKeyDown(ev, this.cell());
    }
}

export const floatToggleGridCell = {
    component: FloatToggleGridCell,
    formatter: formatFloatFactor,
};

registry.category("grid_components").add("float_toggle", floatToggleGridCell);
