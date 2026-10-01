import { expect, queryAllTexts, test } from "@odoo/hoot";
import { Component, xml } from "@odoo/owl";

import { Tab } from "@voip/softphone/tab";

import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

setupVoipTests();

class TestTab extends Component {
    static components = { Tab };
    static template = xml`
        <Tab
            itemsBySection="this.itemsBySection"
            ungroupedItems="this.ungroupedItems"
            state="this.state"
        >
            <t t-set-slot="top"/>
            <t t-set-slot="entry" t-slot-scope="slot">
                <div class="o-test-item" t-att-data-section="slot.section" t-out="slot.item.name"/>
            </t>
        </Tab>
    `;

    itemsBySection = new Map([["Section", [{ id: 1, name: "Grouped item" }]]]);
    state = { searchInputValue: "" };
    ungroupedItems = [{ id: 2, name: "Ungrouped item" }];
}

test("ungrouped items are displayed after grouped items", async () => {
    await mountWithCleanup(TestTab, { noMainContainer: true });

    expect("section h2").toHaveText("Section");
    expect(queryAllTexts(".o-test-item")).toEqual(["Grouped item", "Ungrouped item"]);
    expect(".o-test-item[data-section='ungrouped']").toHaveText("Ungrouped item");
});
