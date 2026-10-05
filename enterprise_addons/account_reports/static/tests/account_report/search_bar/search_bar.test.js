import { expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, Plugin, providePlugins, useProps, xml } from "@odoo/owl";
import { defineModels, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

import { AccountReportSearchBar } from "@account_reports/components/account_report/search_bar/search_bar";

defineModels(mailModels);

async function typeSearch(text) {
    const input = document.querySelector(".o_searchview_input");
    input.value = text;
    input.dispatchEvent(new InputEvent("input", { bubbles: true }));
    await animationFrame();
}

function makeControllerWrapper(lines) {
    class AccountReportController extends Plugin {
        reportLoadingPromise = Promise.resolve();
        lines = lines;
        updateOption(key, value) { expect.step(`updateOption:${key}:${value}`); }
        deleteOption(key) { expect.step(`deleteOption:${key}`); }
        invalidateVisibleLines() { expect.step("invalidateVisibleLines"); }
    }

    class SearchBarWrapper extends Component {
        static template = xml`<AccountReportSearchBar t-props="this.props"/>`;
        static components = { AccountReportSearchBar };
        props = useProps();
        setup() {
            providePlugins([AccountReportController]);
        }
    }
    return SearchBarWrapper;
}

test("non-matching lines get search_match set to false", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Revenue", level: 0 },
        { id: "~account.report~0|~account.report.line~2", name: "Expenses", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));
    await typeSearch("revenue");

    expect(lines[0].search_match).toBe(true);
    expect(lines[1].search_match).toBe(false);
    expect.verifySteps(["updateOption:filter_search_bar:revenue", "invalidateVisibleLines"]);
});

test("search is case-insensitive", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Revenue", level: 0 },
        { id: "~account.report~0|~account.report.line~2", name: "Expenses", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));
    await typeSearch("REVENUE");

    expect(lines[0].search_match).toBe(true);
    expect(lines[1].search_match).toBe(false);
    expect.verifySteps(["updateOption:filter_search_bar:REVENUE", "invalidateVisibleLines"]);
});

test("partial query matches substrings in line names", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Product Sales", level: 0 },
        { id: "~account.report~0|~account.report.line~2", name: "Service Revenue", level: 0 },
        { id: "~account.report~0|~account.report.line~3", name: "Expenses", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));
    await typeSearch("Sales");

    expect(lines[0].search_match).toBe(true);
    expect(lines[1].search_match).toBe(false);
    expect(lines[2].search_match).toBe(false);
    expect.verifySteps(["updateOption:filter_search_bar:Sales", "invalidateVisibleLines"]);
});

test("empty query sets all lines as matching and removes filter option", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Revenue", level: 0 },
        { id: "~account.report~0|~account.report.line~2", name: "Expenses", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));

    // Apply a non-empty search first to put some lines in a non-matching state.
    await typeSearch("revenue");
    expect(lines[0].search_match).toBe(true);
    expect(lines[1].search_match).toBe(false);

    // Clearing the input resets every line to visible.
    await typeSearch("");

    expect(lines[0].search_match).toBe(true);
    expect(lines[1].search_match).toBe(true);
    expect.verifySteps([
        "updateOption:filter_search_bar:revenue",
        "invalidateVisibleLines",
        "deleteOption:filter_search_bar",
        "invalidateVisibleLines",
    ]);
});

test("child match makes ancestor lines visible", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Parent", level: 0 },
        { id: '~account.report~0|~account.report.line~1|{"groupby": "fake"}~res.fake~1', name: "Child Match", level: 1 },
        { id: "~account.report~0|~account.report.line~2", name: "Unrelated", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));
    await typeSearch("child");

    expect(lines[0].search_match).toBe(true);  // Parent becomes visible
    expect(lines[1].search_match).toBe(true);  // Matched line
    expect(lines[2].search_match).toBe(false); // Unrelated top-level sibling
    expect.verifySteps(["updateOption:filter_search_bar:child", "invalidateVisibleLines"]);
});

test("parent match makes all descendant lines visible", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Parent Match", level: 0 },
        { id: '~account.report~0|~account.report.line~1|{"groupby": "fake"}~res.fake~1', name: "Child", level: 1 },
        { id: '~account.report~0|~account.report.line~1|{"groupby": "fake"}~res.fake~1|{"groupby": "fake2"}~res.fake2~1', name: "Grandchild", level: 2 },
        { id: "~account.report~0|~account.report.line~2", name: "Sibling", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));
    await typeSearch("parent");

    expect(lines[0].search_match).toBe(true);  // Matched line
    expect(lines[1].search_match).toBe(true);  // Child carried down
    expect(lines[2].search_match).toBe(true);  // Grandchild carried down
    expect(lines[3].search_match).toBe(false); // Same-level sibling stops propagation
    expect.verifySteps(["updateOption:filter_search_bar:parent", "invalidateVisibleLines"]);
});

test("sibling of matched line does not inherit search_match", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Parent", level: 0 },
        { id: '~account.report~0|~account.report.line~1|{"groupby": "fake"}~res.fake~1', name: "Matching Child", level: 1 },
        { id: '~account.report~0|~account.report.line~1|{"groupby": "fake"}~res.fake~2', name: "Other Child", level: 1 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines));
    await typeSearch("matching");

    expect(lines[0].search_match).toBe(true);  // Parent becomes visible
    expect(lines[1].search_match).toBe(true);  // Matched child
    expect(lines[2].search_match).toBe(false); // Sibling at same level not matched
    expect.verifySteps(["updateOption:filter_search_bar:matching", "invalidateVisibleLines"]);
});

test("initialQuery prop triggers search on mount", async () => {
    const lines = [
        { id: "~account.report~0|~account.report.line~1", name: "Revenue", level: 0 },
        { id: "~account.report~0|~account.report.line~2", name: "Expenses", level: 0 },
    ];
    await mountWithCleanup(makeControllerWrapper(lines), { props: { initialQuery: "revenue" } });
    await animationFrame();

    expect(lines[0].search_match).toBe(true);
    expect(lines[1].search_match).toBe(false);
    expect.verifySteps(["updateOption:filter_search_bar:revenue", "invalidateVisibleLines"]);
});
