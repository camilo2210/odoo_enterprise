import { describe, expect, test } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { mailModels } from "@mail/../tests/mail_test_helpers";
import {
    defineModels,
    fields,
    models,
    mountView,
    onRpc,
    serverState,
} from "@web/../tests/web_test_helpers";

const INSTITUTIONS = [
    { id: 1, name: "Fake Bank", picture: "/fake_bank.png" },
    { id: 2, name: "Other Bank", picture: "/other_bank.png" },
];

class AccountJournal extends models.Model {
    _name = "account.journal";

    name = fields.Char();

    _records = Array.from({ length: 5 }, (_, index) => ({
        id: index + 1,
        name: `Bank ${index + 1}`,
    }));
}

defineModels({ ...mailModels, AccountJournal });

describe.current.tags("desktop");

test("institutions are fetched once for every journal of a company", async () => {
    // The hook caches per company for the lifetime of the page, so the request
    // is only observable from a company no other test has fetched.
    serverState.companies = [
        { id: 37, name: "Bank Configure Co", sequence: 1, parent_id: false, child_ids: [] },
    ];

    onRpc("account.journal", "fetch_online_sync_favorite_institutions", () => {
        expect.step("fetch_online_sync_favorite_institutions");
        return INSTITUTIONS;
    });

    await mountView({
        resModel: "account.journal",
        type: "kanban",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                        <widget name="bank_configure"/>
                    </t>
                </templates>
            </kanban>
        `,
    });
    await waitFor("img[title='Fake Bank']");

    expect(".bank_configure_container").toHaveCount(5);
    expect("img[title='Fake Bank']").toHaveCount(5);
    expect("img[title='Other Bank']").toHaveCount(5);
    expect.verifySteps(["fetch_online_sync_favorite_institutions"]);
});
