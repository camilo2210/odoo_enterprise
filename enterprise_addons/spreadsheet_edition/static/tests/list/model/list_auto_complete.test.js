import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { stores, tokenColors } from "@odoo/o-spreadsheet";
import { Partner, Product, defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import {
    insertListInSpreadsheet,
    createSpreadsheetWithList,
} from "@spreadsheet/../tests/helpers/list";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { makeStore, makeStoreWithModel } from "@spreadsheet/../tests/helpers/stores";

describe.current.tags("headless");
defineSpreadsheetModels();

const { CellComposerStore } = stores;

test("ODOO.LIST id", async function () {
    const { store: composer, model } = await makeStore(CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [
            { name: "foo", string: "Foo" },
            { name: "bar", string: "Bar" },
            { name: "date", string: "Date" },
            { name: "product_id", string: "Product" },
        ],
    });
    await animationFrame();
    for (const formula of ["=ODOO.LIST.VALUE(", "=ODOO.LIST.VALUE( ", "=ODOO.LIST.HEADER("]) {
        composer.startEdition(formula);
        await animationFrame();
        const proposals = composer.autoCompleteProposals;
        expect(proposals).toEqual([
            {
                description: "List",
                fuzzySearchKey: "1List",
                htmlContent: [{ color: "#02c39a", value: "1" }],
                text: "1",
                alwaysExpanded: true,
            },
        ]);
        composer.cancelEdition();
    }
});

test("ODOO.LIST id exact match", async function () {
    const { store: composer, model } = await makeStore(CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [
            { name: "foo", string: "Foo" },
            { name: "bar", string: "Bar" },
            { name: "date", string: "Date" },
            { name: "product_id", string: "Product" },
        ],
    });
    await animationFrame();
    composer.startEdition("=ODOO.LIST.VALUE(1");
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("ODOO.LIST field name", async function () {
    const { model } = await createModelWithDataSource();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [
            { name: "product_id", string: "Product" },
            { name: "bar", string: "Bar" },
        ],
    });
    await animationFrame();
    composer.startEdition("=ODOO.LIST.VALUE(1,1,");
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    const allFields = Object.keys(Partner._fields);
    expect(proposals.map((p) => p.text)).toEqual(
        allFields.map((field) => `"${field}"`),
        { message: "all fields are proposed, quoted" }
    );
    // check completely only the first one
    expect(proposals[0]).toEqual({
        description: "Id",
        fuzzySearchKey: 'Id"id"',
        htmlContent: [{ color: "#00a82d", value: '"id"' }],
        text: '"id"',
    });
    composer.insertAutoCompleteValue(proposals[0]);
    await animationFrame();
    expect(composer.currentContent).toBe('=ODOO.LIST.VALUE(1,1,"id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("ODOO.LIST related field name", async function () {
    const { model } = await createSpreadsheetWithList();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=ODOO.LIST.VALUE(1,1,"product_id"');
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    const allFields = Object.keys(Product._fields);
    expect(proposals.map((p) => p.text).sort(String.localeCompare)).toEqual(
        allFields.map((field) => `"product_id.${field}"`).sort(String.localeCompare),
        { message: "all fields are proposed, quoted" }
    );
    // check completely only the first one
    expect(proposals[0]).toEqual({
        description: "Id",
        fuzzySearchKey: 'Id"product_id.id"',
        htmlContent: [{ color: "#00a82d", value: '.id"' }],
        text: '"product_id.id"',
    });
    composer.insertAutoCompleteValue(proposals[0]);
    await animationFrame();
    expect(composer.currentContent).toBe('=ODOO.LIST.VALUE(1,1,"product_id.id"');
    expect(composer.isAutoCompleteDisplayed).toBe(false, { message: "autocomplete closed" });
});

test("ODOO.LIST invalid related field path", async function () {
    const { model } = await createSpreadsheetWithList();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    composer.startEdition('=ODOO.LIST.VALUE(1,1,"product_id.name.name"');
    await animationFrame();
    expect(composer.isAutoCompleteDisplayed).toBe(false);
});

test("ODOO.LIST.HEADER field name", async function () {
    const { model } = await createModelWithDataSource();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [
            { name: "product_id", string: "Product" },
            { name: "bar", string: "Bar" },
        ],
    });
    await animationFrame();
    composer.startEdition("=ODOO.LIST.HEADER(1,");
    await animationFrame();
    const proposals = composer.autoCompleteProposals;
    const allFields = Object.keys(Partner._fields);
    expect(proposals.map((p) => p.text)).toEqual(
        allFields.map((field) => `"${field}"`),
        { message: "all fields are proposed, quoted" }
    );
});

test("ODOO.LIST field name with invalid list id", async function () {
    const { store: composer, model } = await makeStore(CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [
            { name: "foo", string: "Foo" },
            { name: "bar", string: "Bar" },
            { name: "date", string: "Date" },
            { name: "product_id", string: "Product" },
        ],
    });
    await animationFrame();
    for (const listId of ["", "0", "42"]) {
        composer.startEdition(`=ODOO.LIST.VALUE(${listId},1,`);
        await animationFrame();
        expect(composer.isAutoCompleteDisplayed).toBe(false);
        composer.cancelEdition();
    }
});

test("ODOO.LIST field name includes computed columns", async function () {
    const { model } = await createModelWithDataSource();
    const { store: composer } = await makeStoreWithModel(model, CellComposerStore);
    insertListInSpreadsheet(model, {
        model: "partner",
        columns: [{ name: "foo", string: "Foo" }],
    });
    const [listId] = model.getters.getListIds();
    const sheetId = model.getters.getActiveSheetId();
    const listDef = model.getters.getListDefinition(listId);
    model.dispatch("UPDATE_ODOO_LIST", {
        listId,
        list: {
            ...listDef,
            columns: [
                ...listDef.columns,
                {
                    name: "my_computed",
                    string: "My Computed Column",
                    computedBy: { sheetId, formula: "=0" },
                    hidden: false,
                },
            ],
        },
    });
    await animationFrame();
    for (const formula of ["=ODOO.LIST.VALUE(1,1,", "=ODOO.LIST.HEADER(1,"]) {
        composer.startEdition(formula);
        await animationFrame();
        const proposals = composer.autoCompleteProposals;
        const computedProposal = proposals.find((p) => p.text === '"my_computed"');
        expect(computedProposal).toEqual({
            text: '"my_computed"',
            description: "My Computed Column",
            htmlContent: [{ value: '"my_computed"', color: tokenColors.STRING }],
            fuzzySearchKey: '"my_computed"My Computed Column',
        });
        composer.cancelEdition();
    }
});
