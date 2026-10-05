import {
    click,
    contains,
    insertText,
    scroll,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { expect, describe, test } from "@odoo/hoot";
import { animationFrame, runAllTimers } from "@odoo/hoot-mock";
import { openRecentContactSearch, setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { Voip } from "@voip/core/web/voip_service";
import { VOIP_PAGE_SIZE } from "@voip/softphone/softphone_model";
import { mockService, onRpc, patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Scrolling to bottom loads more recent calls", async () => {
    const pyEnv = await startServer();
    await start();
    for (let i = 0; i < 30; ++i) {
        pyEnv["voip.call"].create({
            phone_number: "(501) 884-5252",
            state: "terminated",
            user_id: serverState.userId,
        });
    }

    let rpcCount = 0;
    onRpc("voip.call", "get_recent_phone_calls", () => {
        ++rpcCount;
    });

    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='recent']");
    await contains(".o-voip-TabEntry", { count: VOIP_PAGE_SIZE });
    expect(rpcCount).toBe(1);
    await scroll(".o-voip-History div.overflow-auto", "bottom");
    await contains(".o-voip-TabEntry", { count: VOIP_PAGE_SIZE * 2 });
    expect(rpcCount).toBe(2);
});

test("Recent search term is used to search contacts", async () => {
    const searchTerm = "Bob";
    onRpc("res.partner", "get_contacts", (args) => {
        if (args.kwargs.search_terms === searchTerm) {
            expect.step("get_contacts called with search term");
        }
    });
    await start();
    await openRecentContactSearch(searchTerm);
    await runAllTimers();
    expect.verifySteps(["get_contacts called with search term"]);
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad");
    await click("button[data-tab='recent']");
    await contains(".o-voip-AddressBook");
    await runAllTimers();
    expect.verifySteps(["get_contacts called with search term"]);
});

test("Recent search opens the contacts view in the recent tab", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "Alpha", phone: "+32498111111" },
        { name: "Beta", phone: "+32498222222" },
        { name: "Gamma", phone: "+32498333333" },
    ]);

    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='recent']");
    // History tab should now be active, search inside
    await contains("button[data-tab='recent'].active");
    await insertText("#o-voip-Tab-searchInput", "222");
    // Recent stays active, but the content switches to the contacts view.
    await contains("button[data-tab='recent'].active");
    // First check there is only one match (despite having 3 contacts)...
    await contains(".o-voip-AddressBook .o-voip-TabEntry", { count: 1 });
    // ... then check that it is the right contact
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "Beta" });
});

test("Pasted recent search term is used to search contacts", async () => {
    const pyEnv = await startServer();
    const searchDef = Promise.withResolvers();
    let searchShouldWait = true;
    patchWithCleanup(Voip.prototype, {
        async fetchContacts(params = {}) {
            if (params.searchTerms?.trim() === "200" && params.loadMore) {
                expect.step("fetchContacts 200 loadMore");
            }
            return super.fetchContacts(...arguments);
        },
    });
    onRpc("res.partner", "get_contacts", async (args) => {
        if (args.kwargs.search_terms === "200") {
            expect.step(`get_contacts 200 offset ${args.kwargs.offset}`);
            if (!args.kwargs.offset && searchShouldWait) {
                await searchDef.promise;
            }
        }
        return args.parent();
    });
    pyEnv["res.partner"].create({ name: "Match A Preload", phone: "+1-200-0001" });
    for (let i = 0; i < VOIP_PAGE_SIZE - 1; i++) {
        pyEnv["res.partner"].create({ name: `Preload Filler ${i}`, phone: `+1-555-00${i}` });
    }
    pyEnv["res.partner"].create([
        { name: "Match B", phone: "+1-200-0002" },
        { name: "Match C", phone: "+1-200-0003" },
        { name: "Match D", phone: "+1-200-0004" },
    ]);

    await start();
    await openRecentContactSearch("Preload");
    await runAllTimers();
    await contains(".o-voip-AddressBook .o-voip-TabEntry", { count: VOIP_PAGE_SIZE });

    let input = document.querySelector("#o-voip-Tab-searchInput");
    input.value = "";
    input.dispatchEvent(
        new InputEvent("input", { bubbles: true, data: null, inputType: "deleteContentBackward" })
    );
    await animationFrame();
    await contains(".o-voip-History");

    input = document.querySelector("#o-voip-Tab-searchInput");
    input.value = "200";
    input.dispatchEvent(
        new InputEvent("input", { bubbles: true, data: "200", inputType: "insertFromPaste" })
    );
    await animationFrame();
    await contains(".o-voip-AddressBook");
    await contains(".o-voip-AddressBook .o-voip-TabEntry", { count: 1 });
    await expect.waitForSteps(["get_contacts 200 offset 0", "fetchContacts 200 loadMore"]);
    expect.verifySteps([]);
    searchShouldWait = false;
    searchDef.resolve();
    await runAllTimers();

    await contains(".o-voip-AddressBook .o-voip-TabEntry", { count: 4 });
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "Match A Preload" });
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "Match B" });
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "Match C" });
    await contains(".o-voip-AddressBook .o-voip-TabEntry-title", { text: "Match D" });
});

test("Contact history action shows recent calls with that contact", async () => {
    const pyEnv = await startServer();
    const partnerAId = pyEnv["res.partner"].create({
        name: "AAA",
        phone: "+32498111111",
    });
    const partnerBId = pyEnv["res.partner"].create({
        name: "BBB",
        phone: "+32498222222",
    });
    pyEnv["voip.call"].create([
        {
            phone_number: "+32498111111",
            partner_id: partnerAId,
            state: "terminated",
            user_id: serverState.userId,
        },
        {
            phone_number: "+32498222222",
            partner_id: partnerBId,
            state: "terminated",
            user_id: serverState.userId,
        },
        {
            phone_number: "+32498111111",
            partner_id: partnerAId,
            state: "terminated",
            user_id: serverState.userId,
        },
    ]);
    onRpc("voip.call", "get_recent_phone_calls", (args) => {
        if (args.kwargs.partner_id === partnerAId) {
            expect.step("get_recent_phone_calls called with partner");
        }
    });
    mockService("action", {
        doAction(action) {
            expect.step("open full history");
            expect(action.context.search_default_partner_id).toBe(partnerAId);
            expect(action.context.search_default_my_calls).toBe(1);
        },
    });

    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='recent']");
    await contains(
        ".o-voip-History button[title='Open full history'] > [data-icon='expand_content']"
    );
    await insertText("#o-voip-Tab-searchInput", "AAA");
    await runAllTimers();
    await click(".o-voip-AddressBook .o-voip-TabEntry:contains('AAA')");
    await click(".o-voip-AddressBook .o-voip-TabEntry:contains('AAA') button[title='History']");

    expect.verifySteps(["get_recent_phone_calls called with partner"]);
    await contains("button[data-tab='recent'].active");
    await contains(".o-voip-AddressBook", { count: 0 });
    await contains(".o-voip-History", { text: "Calls with AAA" });
    await contains(".o-voip-History input[placeholder='Search contacts…']", { count: 0 });
    await contains(
        ".o-voip-History button[title='Open full history'] > [data-icon='expand_content']"
    );
    await contains(".o-voip-History .o-voip-TabEntry", { count: 2 });
    await contains(".o-voip-History .o-voip-TabEntry:contains('AAA')", { count: 2 });
    await contains(".o-voip-History .o-voip-TabEntry:contains('BBB')", { count: 0 });
    await click(".o-voip-History .o-voip-TabEntry:contains('AAA'):eq(0)");
    await contains(".o-voip-History .o-voip-TabEntry:contains('AAA') button[title='History']", {
        count: 0,
    });
    await click(".o-voip-History button[title='Show all recent calls']");
    await contains(".o-voip-History input[placeholder='Search contacts…']");
    await contains(".o-voip-History .o-voip-TabEntry", { count: 3 });
    await click(".o-voip-History .o-voip-TabEntry:contains('AAA') button[title='History']:eq(0)");
    expect.verifySteps(["get_recent_phone_calls called with partner"]);
    await contains(".o-voip-History", { text: "Calls with AAA" });
    await contains(".o-voip-History details[open]", { count: 0 });
    await click(".o-voip-History button[title='Open full history']");
    expect.verifySteps(["open full history"]);
});

test("Show log button no matter if there is a contact", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({ name: "Muamua", phone: "332" });
    pyEnv["voip.call"].create([
        {
            phone_number: "233",
            state: "terminated",
            user_id: serverState.userId,
        },
        {
            phone_number: "332",
            partner_id: partnerId,
            state: "terminated",
            user_id: serverState.userId,
        },
    ]);
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click(".o-voip-Softphone-navItem span:text('Recent')");
    await click(".o-voip-TabEntry-title:text('233')");
    await contains(".o-voip-TabEntry:has(span:text('233')):has(button[title='Log'])");
    await click(".o-voip-TabEntry-title:text('Muamua')");
    await contains(".o-voip-TabEntry:has(span:text('Muamua')):has(button[title='Log'])");
});
