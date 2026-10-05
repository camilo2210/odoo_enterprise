import { expect, test } from "@odoo/hoot";
import { registries } from "@odoo/o-spreadsheet";
import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { defineSpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { getEvaluatedCell } from "@spreadsheet/../tests/helpers/getters";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { patchSpreadsheetExternalShareFunctionCheck } from "@documents_spreadsheet/bundle/actions/external_share_function";

registries.functionRegistry
    .add("TEST.SHARE.COMPUTE", {
        description: "Test function using `compute`, for external share check tests.",
        args: [],
        category: "Odoo",
        compute: () => ({ value: "result" }),
    })
    .add("TEST.SHARE.COMPUTE.ARRAY", {
        description: "Test function using `computeArray`, for external share check tests.",
        args: [],
        category: "Odoo",
        computeArray: () => [[{ value: "result" }]],
    });

defineSpreadsheetModels();
patchSpreadsheetExternalShareFunctionCheck();

async function evaluate(isSharedExternally, formula) {
    const { model } = await createModelWithDataSource({
        modelConfig: { custom: { env: { isSharedExternally: () => isSharedExternally } } },
    });
    setCellContent(model, "A1", formula);
    return getEvaluatedCell(model, "A1");
}

test("Function using 'compute' works normally, and is blocked when shared externally", async function () {
    expect((await evaluate(false, "=TEST.SHARE.COMPUTE()")).value).toBe("result");
    expect((await evaluate(true, "=TEST.SHARE.COMPUTE()")).message).toBe(
        "TEST.SHARE.COMPUTE is not available in spreadsheets shared externally."
    );
});

test("Function using 'computeArray' works normally, and is blocked when shared externally", async function () {
    expect((await evaluate(false, "=TEST.SHARE.COMPUTE.ARRAY()")).value).toBe("result");
    expect((await evaluate(true, "=TEST.SHARE.COMPUTE.ARRAY()")).message).toBe(
        "TEST.SHARE.COMPUTE.ARRAY is not available in spreadsheets shared externally."
    );
});
