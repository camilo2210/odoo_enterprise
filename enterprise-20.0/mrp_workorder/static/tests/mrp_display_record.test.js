import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { after, describe, expect, test } from "@odoo/hoot";
import { markup } from "@odoo/owl";
import { contains, mockService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { MrpDisplayRecord } from "@mrp_workorder/mrp_display/mrp_display_record";

describe.current.tags("desktop");
defineMailModels();

/**
 * The shop floor feeds MrpDisplayRecord with relational model records. A plain
 * object exposing the same fields is enough to render a card, as MrpDisplay
 * already does for its showcase records (see `demoMORecords`).
 */
const FAKE_PRODUCTION = {
    id: 1,
    resModel: "mrp.production",
    data: {
        check_ids: { records: [] },
        display_name: "WH/MO/00001",
        employee_ids: { records: [], resIds: [] },
        move_byproduct_ids: { records: [] },
        move_raw_ids: { records: [] },
        name: "WH/MO/00001",
        picking_type_auto_close: false,
        priority: "0",
        product_description_variants: "",
        product_id: { id: 1, display_name: "Table" },
        product_qty: 1,
        product_tracking: false,
        qty_producing: 0,
        state: "progress",
        uom_id: { id: 1, display_name: "Units" },
        workorder_ids: { records: [] },
    },
    fields: {
        priority: {
            type: "selection",
            selection: [
                ["0", "Normal"],
                ["1", "Urgent"],
            ],
        },
        state: { type: "selection", selection: [["progress", "In Progress"]] },
    },
};

const FAKE_PROPS = {
    groups: { byproducts: false, timer: false, uom: false, workorders: false },
    removeFromCache: () => {},
    sessionOwner: {},
    updateEmployees: () => {},
    workcenters: [],
    updateWorkcenter: () => {},
};

function mountProductionCard(data = {}) {
    const production = { ...FAKE_PRODUCTION, data: { ...FAKE_PRODUCTION.data, ...data } };
    return mountWithCleanup(MrpDisplayRecord, {
        componentEnv: { reload: () => {} },
        props: { ...FAKE_PROPS, production, record: production },
    });
}

test("clicking a note link opens it in a new tab instead of the note editor", async () => {
    mockService("dialog", { add: () => expect.step("note editor") });
    // Keep the test runner on the page: prevent the link's actual navigation.
    const preventNavigation = (ev) => {
        if (ev.target.closest("a[href]")) {
            ev.preventDefault();
        }
    };
    document.addEventListener("click", preventNavigation, { capture: true });
    after(() => document.removeEventListener("click", preventNavigation, { capture: true }));

    await mountProductionCard({
        note: markup(`<p>See <a href="/web/content/1?download=true">quote.pdf</a></p>`),
    });

    expect(".o_mrp_record_line a").toHaveAttribute("target", "_blank");
    expect(".o_mrp_record_line a").toHaveAttribute("rel", "noreferrer");

    await contains(".o_mrp_record_line a").click();
    expect.verifySteps([]);

    // The pencil is a deterministic click target inside the note, unlike the
    // note's own center which may land on the link.
    await contains(".o_mrp_record_line [data-icon='edit_square']").click();
    expect.verifySteps(["note editor"]);
});
