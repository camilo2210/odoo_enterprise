import { Component, computed, signal, t, useEffect, useProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/core/utils/numbers";
import { formatInteger } from "@web/views/fields/formatters";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { parseFloat, parseInteger } from "@web/views/fields/parsers";
import { standardGridCellProps, useGridCell } from "@web_grid/hooks/grid_cell_hook";
import { useInputHook } from "@web_grid/hooks/input_hook";
import { GridCell as ModelGridCell } from "../views/grid_model";

export class GridCell extends Component {
    static template = "web_grid.Cell";

    props = useProps(standardGridCellProps);

    rootRef = signal.ref(HTMLDivElement);
    inputRef = signal.ref(HTMLInputElement);

    discardChanges = false;
    inputMode = "numeric";
    cell = signal(null, { type: t.or([t.instanceOf(ModelGridCell), t.literal(null)]) });
    invalid = signal(false);

    formattedValue = computed(() => {
        const { type, digits } = this.props.fieldInfo;
        if (type === "integer") {
            return formatInteger(this.value());
        }
        return formatFloat(this.value(), { digits: digits || 2 });
    });
    isEditable = computed(() => {
        const cell = this.cell();
        return !this.props.readonly && cell?.readonly === false && !cell.row.isSection;
    });
    value = computed(this.getCellValue.bind(this));

    gridCellHook = useGridCell(this.cell, this.isEditable);

    setup() {
        useNumpadDecimal(this.inputRef);
        useEffect(() => {
            this.props.cell(); // subscribe to cell value
            this.discardChanges = false;
            const inputEl = this.inputRef();
            if (inputEl) {
                inputEl.value = this.formattedValue();
            }
            if (this.props.editMode && inputEl) {
                inputEl.focus();
                if (inputEl.type === "text") {
                    if (inputEl.selectionStart === null) {
                        return;
                    }
                    if (inputEl.selectionStart === inputEl.selectionEnd) {
                        inputEl.selectionStart = 0;
                        inputEl.selectionEnd = inputEl.value.length;
                    }
                }
            }
        });
        useInputHook({
            inputRef: this.inputRef,
            invalid: this.invalid,
            value: this.formattedValue,
            discard: this.discard.bind(this),
            onChange: this.onChange.bind(this),
            onCommit: this.saveEdition.bind(this),
            onKeyDown: (ev) => this.props.onKeyDown(ev, this.cell()),
            parse: this.parse.bind(this),
        });
    }

    getCellValue() {
        return this.cell()?.value || 0;
    }

    /**
     * @param {string} value
     */
    parse(value) {
        if (this.props.fieldInfo.type === "integer") {
            return parseInteger(value);
        }
        return parseFloat(value);
    }

    onChange(value) {
        if (!this.discardChanges) {
            this.update(value);
        }
    }

    update(value) {
        this.cell().update(value);
    }

    saveEdition(value) {
        const changesCommitted = (value || false) !== (this.cell().value || false);
        if ((value || false) !== (this.cell()?.value || false)) {
            this.update(value);
        }
        this.props.onEdit(false);
        return changesCommitted;
    }

    discard() {
        this.discardChanges = true;
        this.props.onEdit(false);
    }

    onCellClick(ev) {
        if (this.isEditable() && !this.props.editMode) {
            this.discardChanges = false;
            this.props.onEdit(true);
        }
    }
}

export const integerGridCell = {
    component: GridCell,
    formatter: formatInteger,
};

registry.category("grid_components").add("integer", integerGridCell);

export const floatGridCell = {
    component: GridCell,
    formatter: formatFloat,
};

registry.category("grid_components").add("float", floatGridCell);
