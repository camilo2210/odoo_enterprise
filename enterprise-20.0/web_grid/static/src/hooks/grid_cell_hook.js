import { signal, t, useEffect, useProps } from "@odoo/owl";
import { GridCell } from "../views/grid_model";

/**
 * @param {import("@odoo/owl").Signal<GridCell>} cell
 * @param {import("@odoo/owl").ReactiveValue<boolean>} isEditable
 */
export function useGridCell(cell, isEditable) {
    function onMagnifierGlassClick() {
        const { context, domain, title } = cell();
        props.openRecords(title, domain.toList(), context);
    }

    const rootRef = signal.ref();
    const props = useProps(standardGridCellProps);

    useEffect(function updateGridCell() {
        const cellEl = props.cell();
        const rootEl = rootRef();
        if (!cellEl || !rootEl) {
            return cell.set(null);
        }
        const gridCell = props.getCell(cellEl.dataset.row, cellEl.dataset.column);
        cell.set(gridCell);
        if (!gridCell) {
            return;
        }
        Object.assign(rootEl.style, {
            "grid-row": cellEl.style["grid-row"],
            "grid-column": cellEl.style["grid-column"],
            "z-index": 1,
        });
        rootEl.dataset.gridRow = cellEl.dataset.gridRow;
        rootEl.dataset.gridColumn = cellEl.dataset.gridColumn;
        rootEl.classList.toggle(
            "o_field_cursor_disabled",
            !gridCell.row.isSection && !isEditable()
        );
        rootEl.classList.toggle("fw-bold", Boolean(gridCell.row.isSection));
        cellEl.querySelector(".o_grid_cell_readonly").classList.add("d-none");
    });

    return { onMagnifierGlassClick, rootRef };
}

export const standardGridCellProps = {
    name: t.string(),
    cell: t.signal(t.ref()),
    classNames: t.string(),
    fieldInfo: t.object(),
    readonly: t.boolean().optional(true),
    editMode: t.boolean().optional(false),
    openRecords: t.function(),
    onEdit: t.function(),
    getCell: t.function([], t.instanceOf(GridCell)),
    onKeyDown: t.function().optional(),
};
