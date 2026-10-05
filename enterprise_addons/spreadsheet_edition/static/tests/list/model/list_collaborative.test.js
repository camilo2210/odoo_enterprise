import { beforeEach, describe, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { addRows, setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels, getBasicServerData } from "@spreadsheet/../tests/helpers/data";
import {
    getCellContent,
    getCellFormula,
    getCellValue,
} from "@spreadsheet/../tests/helpers/getters";
import { waitForDataLoaded } from "@spreadsheet/helpers/model";
import { ListCoreViewPlugin } from "@spreadsheet/list";
import {
    setupCollaborativeEnv,
    spExpect,
} from "@spreadsheet_edition/../tests/helpers/collaborative_helpers";

describe.current.tags("headless");
defineSpreadsheetModels();

/** @typedef {import("@spreadsheet/o_spreadsheet/o_spreadsheet").Model} Model */

function insertList(model, listId, anchor = [0, 0]) {
    const definition = getListPayload();

    return model.dispatch("INSERT_ODOO_LIST", {
        sheetId: model.getters.getActiveSheetId(),
        col: anchor[0],
        row: anchor[1],
        definition,
        listId,
        linesNumber: 5,
        mode: "static",
    });
}

function getListPayload() {
    return {
        model: "partner",
        columns: [
            { name: "foo", string: "Foo" },
            { name: "probability", string: "Probability" },
        ],
        domain: [],
        context: {},
        orderBy: [],
    };
}

let alice, bob, charlie, network;

beforeEach(async () => {
    ({ alice, bob, charlie, network } = await setupCollaborativeEnv(getBasicServerData()));
});

test("Add a list", async () => {
    insertList(alice, "1");
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds().length,
        1
    );
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => getCellValue(user, "A4"),
        "Loading..."
    );
    await animationFrame();
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue((user) => getCellValue(user, "A4"), 17);
});

test("Add two lists concurrently", async () => {
    await network.concurrent(() => {
        insertList(alice, "1");
        insertList(bob, "1", [0, 25]);
    });
    await waitForDataLoaded(alice);
    await waitForDataLoaded(bob);
    await waitForDataLoaded(charlie);
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds(),
        ["1", "2"]
    );
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => getCellFormula(user, "A1"),
        `=ODOO.LIST.HEADER(1,"foo","Foo")`
    );
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => getCellFormula(user, "A26"),
        `=ODOO.LIST.HEADER(2,"foo","Foo")`
    );
    await animationFrame();

    spExpect([alice, bob, charlie]).toHaveSynchronizedValue((user) => getCellValue(user, "A4"), 17);
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => getCellValue(user, "A29"),
        17
    );
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue((user) => {
        const UIPlugin = user["handlers"].find(
            (handler) => handler instanceof ListCoreViewPlugin,
            undefined
        );
        return Object.keys(UIPlugin.lists).length;
    }, 2);
});

test("Can undo a command before a INSERT_ODOO_LIST", async () => {
    setCellContent(bob, "A10", "Hello Alice");
    insertList(alice, "1");
    setCellContent(charlie, "A11", "Hello all");
    bob.dispatch("REQUEST_UNDO");
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => getCellContent(user, "A10"),
        ""
    );
});

test("Rename and remove a list concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        alice.dispatch("RENAME_ODOO_LIST", {
            listId: "1",
            name: "test",
        });
        bob.dispatch("REMOVE_ODOO_LIST", {
            listId: "1",
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds().length,
        0
    );
});

test("Re-insert and remove a list concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        const definition = getListPayload();
        alice.dispatch("RE_INSERT_ODOO_LIST", {
            listId: "1",
            col: 0,
            row: 0,
            sheetId: alice.getters.getActiveSheetId(),
            linesNumber: 5,
            columns: definition.columns,
        });
        bob.dispatch("REMOVE_ODOO_LIST", {
            listId: "1",
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds().length,
        0
    );
});

test("remove and update a domain of a list concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        alice.dispatch("REMOVE_ODOO_LIST", {
            listId: "1",
        });
        bob.dispatch("UPDATE_ODOO_LIST_DOMAIN", {
            listId: "1",
            domain: [["foo", "in", [55]]],
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds().length,
        0
    );
});

test("remove and update a sorting of a list concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        const listDefinition = alice.getters.getListDefinition("1");
        alice.dispatch("REMOVE_ODOO_LIST", {
            listId: "1",
        });
        const orderBy = [{ name: "foo", asc: true }];
        bob.dispatch("UPDATE_ODOO_LIST", {
            listId: "1",
            list: {
                ...listDefinition,
                orderBy: orderBy,
            },
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds().length,
        0
    );
});

test("Duplicate and remove list at the same time concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        bob.dispatch("REMOVE_ODOO_LIST", {
            listId: "1",
        });
        alice.dispatch("DUPLICATE_ODOO_LIST", {
            listId: "1",
            newListId: "2",
        });
    });
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds().length,
        0
    );
});

test("Duplicate list concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        bob.dispatch("DUPLICATE_ODOO_LIST", {
            listId: "1",
            newListId: "2",
        });
        alice.dispatch("DUPLICATE_ODOO_LIST", {
            listId: "1",
            newListId: "2",
        });
    });
    const expectedListIds = ["1", "2", "3"];
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds(),
        expectedListIds
    );
});

test("Duplicate and insert list concurrently", async () => {
    insertList(alice, "1");
    await network.concurrent(() => {
        bob.dispatch("DUPLICATE_ODOO_LIST", {
            listId: "1",
            newListId: "2",
        });
        insertList(alice, "2");
    });
    const expectedListIds = ["1", "2", "3"];
    spExpect([alice, bob, charlie]).toHaveSynchronizedValue(
        (user) => user.getters.getListIds(),
        expectedListIds
    );
});

test("Computed column formula in UPDATE_ODOO_LIST is adapted when rows are added concurrently before", async () => {
    insertList(alice, "1");
    const sheetId = alice.getters.getActiveSheetId();
    const listDef = alice.getters.getListDefinition("1");

    await network.concurrent(() => {
        addRows(bob, "before", 0, 1);
        alice.dispatch("UPDATE_ODOO_LIST", {
            listId: "1",
            list: {
                ...listDef,
                columns: [
                    ...listDef.columns,
                    {
                        name: "calc",
                        string: "Calc",
                        computedBy: { sheetId, formula: "=A1" },
                        hidden: false,
                    },
                ],
            },
        });
    });

    spExpect([alice, bob, charlie]).toHaveSynchronizedValue((user) => {
        const def = user.getters.getListDefinition("1");
        const calcCol = def.columns.find((col) => col.name === "calc");
        return calcCol?.computedBy?.formula;
    }, "=A2");
});

test("Computed column formula in UPDATE_ODOO_LIST is adapted when rows are added concurrently after", async () => {
    insertList(alice, "1");
    const sheetId = alice.getters.getActiveSheetId();
    const listDef = alice.getters.getListDefinition("1");

    await network.concurrent(() => {
        alice.dispatch("UPDATE_ODOO_LIST", {
            listId: "1",
            list: {
                ...listDef,
                columns: [
                    ...listDef.columns,
                    {
                        name: "calc",
                        string: "Calc",
                        computedBy: { sheetId, formula: "=A1" },
                        hidden: false,
                    },
                ],
            },
        });
        addRows(bob, "before", 0, 1);
    });

    spExpect([alice, bob, charlie]).toHaveSynchronizedValue((user) => {
        const def = user.getters.getListDefinition("1");
        const calcCol = def.columns.find((col) => col.name === "calc");
        return calcCol?.computedBy?.formula;
    }, "=A2");
});
