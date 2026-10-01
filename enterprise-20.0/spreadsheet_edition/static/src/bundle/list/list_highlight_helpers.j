import { helpers, stores } from "@odoo/o-spreadsheet";

const { positionToZone, mergeContiguousZones } = helpers;
const { ViewportsStore } = stores;

export function getListHighlights(env, listId) {
    const getters = env.model.getters;
    const sheetId = getters.getActiveSheetId();
    const listCellPositions = getVisibleListCellPositions(env, listId);
    const mergedZones = mergeContiguousZones(listCellPositions.map(positionToZone));
    return mergedZones.map((zone) => ({
        range: getters.getRangeFromZone(sheetId, zone),
        noFill: true,
    }));
}

function getVisibleListCellPositions(env, listId) {
    const getters = env.model.getters;
    const viewStore = env.getStore(ViewportsStore);
    const positions = [];
    const sheetId = getters.getActiveSheetId();
    for (const col of viewStore.visibleCols) {
        for (const row of viewStore.visibleRows) {
            const position = { sheetId, col, row };
            const cellListId = getters.getListIdFromPosition(position);
            if (listId === cellListId) {
                positions.push(position);
            }
        }
    }
    return positions;
}
