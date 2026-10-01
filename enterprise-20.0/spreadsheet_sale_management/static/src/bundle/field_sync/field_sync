import { astToFormula, helpers, stores } from "@odoo/o-spreadsheet";
import { getFirstListFunction } from "@spreadsheet/list/list_helpers";

const { positionToZone } = helpers;

const { SpreadsheetStore, HighlightStore, DelayedHoveredCellStore, ViewportsStore } = stores;

export class FieldSyncHighlightStore extends SpreadsheetStore {
    viewStore = this.get(ViewportsStore);

    constructor(get) {
        super(get);
        this.hoveredCell = get(DelayedHoveredCellStore);
        const highlightStore = get(HighlightStore);
        highlightStore.register(this);
        this.onDispose(() => {
            highlightStore.unRegister(this);
        });
    }

    get highlights() {
        if (this.hoveredCell.col === undefined || this.hoveredCell.row === undefined) {
            return [];
        }
        const sheetId = this.getters.getActiveSheetId();
        const fieldSync = this.getters.getFieldSync({
            sheetId,
            col: this.hoveredCell.col,
            row: this.hoveredCell.row,
        });
        if (!fieldSync) {
            return [];
        }
        const highlights = [];
        for (const cell of this.getters.getCells(sheetId)) {
            const cellPosition = this.getters.getCellPosition(cell.id);
            if (
                cell.isFormula &&
                this.viewStore.viewports.isPixelPositionVisible(sheetId, cellPosition)
            ) {
                const listFunction = getFirstListFunction(cell.compiledFormula, this.getters);
                if (!listFunction) {
                    continue;
                }
                const [listIdArg, positionArg, fieldNameArg] = listFunction.args;
                if (!listIdArg || !positionArg || !fieldNameArg) {
                    continue;
                }
                const listId = this.getters
                    .evaluateFormula(sheetId, astToFormula(listIdArg))
                    ?.toString();
                const position = this.getters.evaluateFormula(sheetId, astToFormula(positionArg));
                const fieldName = this.getters.evaluateFormula(sheetId, astToFormula(fieldNameArg));
                if (
                    listId === fieldSync.listId &&
                    position - 1 === fieldSync.indexInList &&
                    fieldName === fieldSync.fieldName
                ) {
                    highlights.push({
                        range: this.getters.getRangeFromZone(sheetId, positionToZone(cellPosition)),
                        sheetId,
                        color: "#875A7B",
                    });
                }
            }
        }
        return highlights;
    }
}
