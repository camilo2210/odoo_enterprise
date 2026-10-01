function generateReinsertListChildren(mode) {
    return (env) =>
        env.model.getters.getListIds().map((listId, index) => ({
            id: `reinsert_${mode}_list_${listId}`,
            name: env.model.getters.getListDisplayName(listId),
            sequence: index,
            isVisible: (env) => env.model.getters.getListDataSource(listId).isModelValid(),
            execute: async (env) => {
                const zone = env.model.getters.getSelectedZone();
                const list = env.model.getters.getListDefinition(listId);
                const columns = list.columns.map((column) => ({
                    name: column.name,
                    string: column.string,
                }));
                env.getLinesNumber((linesNumber) => {
                    env.model.dispatch("RE_INSERT_ODOO_LIST_WITH_TABLE", {
                        sheetId: env.model.getters.getActiveSheetId(),
                        col: zone.left,
                        row: zone.top,
                        listId,
                        linesNumber,
                        columns: columns,
                        mode: mode,
                    });
                });
            },
        }));
}

export const REINSERT_STATIC_LIST_CHILDREN = generateReinsertListChildren("static");
export const REINSERT_DYNAMIC_LIST_CHILDREN = generateReinsertListChildren("dynamic");
