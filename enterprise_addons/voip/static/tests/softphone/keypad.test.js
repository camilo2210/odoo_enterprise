import { describe, expect, runAllTimers, test } from "@odoo/hoot";
import { advanceTime, edit, press, queryFirst, queryOne, tick } from "@odoo/hoot-dom";
import { ImStatusMixin } from "@mail/core/common/im_status_mixin";
import {
    click,
    contains,
    insertText,
    start,
    startServer,
    triggerHotkey,
} from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { serializeDateTime } from "@web/core/l10n/dates";
import { getService, onRpc, serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

function notifySelectionChange() {
    document.dispatchEvent(new Event("selectionchange"));
}

test.tags("focus required");
test("input is focused when opening the keypad", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar input:focus");
});

test.tags("focus required");
test("country selector filter input is auto-focused when opening dropdown", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await click(".o-voip-Keypad-searchBar .o-voip-countryFlag");
    await contains(".o-voip-countryDropdown-search input:focus");
});

test.tags("focus required");
test("input is persisted when closing then re-opening the keypad", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "513");
    await contains("button[data-tab='recent']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar input:value(513)");
});

test.tags("focus required");
test("“backspace button” deletes the last character of the not focused input", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "123");
    const input = document.querySelector(".o-voip-Keypad-searchBar input:focus");
    input.blur();
    await click(".o-voip-Keypad-searchBar button[title=Backspace]");
    await contains(".o-voip-Keypad-searchBar input:value(12)");
});

test.tags("focus required");
test("“backspace button” deletes characters from cursor position", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "01123456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(3, 3);
    // manually notify useSelection that the selection changed programmatically
    notifySelectionChange();
    await click(".o-voip-Keypad-searchBar button[title=Backspace]");
    expect(input.selectionStart).toBe(2);
    expect(input.selectionEnd).toBe(2);
    await contains(".o-voip-Keypad-searchBar input:value(0123456)");
});

test.tags("focus required");
test("“backspace button” deletes selected characters", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "011123456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(2, 4);
    notifySelectionChange();
    await click(".o-voip-Keypad-searchBar button[title=Backspace]");
    expect(input.selectionStart).toBe(2);
    expect(input.selectionEnd).toBe(2);
    await contains(".o-voip-Keypad-searchBar input:value(0123456)");
});

test.tags("focus required");
test("“backspace button” does nothing when the cursor is at the beginning of the input", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "0123456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(0, 0);
    notifySelectionChange();
    await click(".o-voip-Keypad-searchBar button[title=Backspace]");
    expect(input.selectionStart).toBe(0);
    expect(input.selectionEnd).toBe(0);
    await contains(".o-voip-Keypad-searchBar input:value(0123456)");
});

test.tags("focus required");
test("backspace button long press clears the entire keypad input", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");

    async function checkBackspaceLongPress() {
        const backspaceBtnEl = document.querySelector(".o-voip-Keypad-backspace");
        backspaceBtnEl.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
        await advanceTime(500);
        backspaceBtnEl.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
        await contains(".o-voip-Keypad-searchBar input:empty");
    }

    await insertText(".o-voip-Keypad-searchBar input", "0123456");
    await checkBackspaceLongPress();

    await insertText(".o-voip-Keypad-searchBar input", "0123456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(2, 4);
    notifySelectionChange();
    expect(input.selectionStart).toBe(2);
    expect(input.selectionEnd).toBe(4);
    await checkBackspaceLongPress();
});

test.tags("focus required");
test("clicking on a key appends it to the end of the not focused input", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "123");
    const input = document.querySelector(".o-voip-Keypad-searchBar input:focus");
    input.blur();
    await click(".o-voip-Keypad-digit:contains(0)");
    await contains(".o-voip-Keypad-searchBar input:value(1230)");
});

test.tags("focus required");
test("input is focused back after clicking on a key", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await click(".o-voip-Keypad-digit:contains(2)");
    await contains(".o-voip-Keypad-searchBar input:focus");
});

test.tags("focus required");
test("clicking on a key inserts the key behind the cursor", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "023456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(1, 1);
    notifySelectionChange();
    await click(".o-voip-Keypad-digit:contains(1)");
    expect(input.selectionStart).toBe(2);
    expect(input.selectionEnd).toBe(2);
    await contains(".o-voip-Keypad-searchBar input:value(0123456)");
});

test.tags("focus required");
test("cursor selection is replaced by the clicked key", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "0223456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(1, 2);
    notifySelectionChange();
    await click(".o-voip-Keypad-digit:contains(1)");
    expect(input.selectionStart).toBe(2);
    expect(input.selectionEnd).toBe(2);
    await contains(".o-voip-Keypad-searchBar input:value(0123456)");
});

test.tags("focus required");
test("pressing Enter in the input calls the dialed number", async () => {
    const pyEnv = await startServer();
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "9223372036854775807");
    await triggerHotkey("Enter");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "9223372036854775807"]])).toBe(1);
});

test.tags("focus required");
test("pressing Enter in the input doesn't make a call if the trimmed input is empty", async () => {
    const pyEnv = await startServer();
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "\t \n\r\v");
    await triggerHotkey("Enter");
    expect(pyEnv["voip.call"].search_count([])).toBe(0);
});

test("Search by T9 code works", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1234567890", t9_name: " 5646 363" },
        { name: "Jane Smith", phone: "+1987654321", t9_name: " 5263 76484" },
        { name: "Bob Wilson", phone: "+1122334455", t9_name: " 262 94576" },
    ]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    // T9 search with no results
    await insertText(".o-voip-Keypad-input", "99999");
    await contains(".o-voip-Keypad .d-flex.flex-column.mx-3", { count: 0 });
    // T9 search that should find results
    await insertText(".o-voip-Keypad-input", "5646", { replace: true });
    await contains(".o-voip-Keypad button:contains(John Doe)");
    // T9 search for last name match
    await insertText(".o-voip-Keypad-input", "76484", { replace: true });
    await contains(".o-voip-Keypad button:contains(Jane Smith)");
});

test("Keypad suggestion highlights matching T9 name and phone number", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "John Doe",
        phone: "+1 5646 7890",
        t9_name: " 5646 363",
    });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "5646");

    await contains(".o-voip-Keypad button.btn-light .o-voip-highlighted-letter", { count: 2 });
    await contains(".o-voip-Keypad button.btn-light .o-voip-highlighted-letter:eq(0)", {
        text: "John",
    });
    await contains(".o-voip-Keypad button.btn-light .o-voip-highlighted-letter:eq(1)", {
        text: "5646",
    });
});

test("Keypad suggestion and AddressBook use the same contact order", async () => {
    const pyEnv = await startServer();
    const marcId = pyEnv["res.partner"].create({
        name: "Marc Demo",
        phone: "+1-555-2001",
    });
    pyEnv["res.partner"].create({
        name: "Adele",
        phone: "+1-555-2002",
    });
    await start();
    getService("mail.store").insert({
        "res.partner": [
            {
                id: marcId,
                complete_name: "Marc Demo",
                name: "Marc Demo",
                phone: "+1-555-2001",
            },
        ],
    });
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "de");
    await runAllTimers();

    await contains(".o-voip-Keypad button.btn-light:contains(Adele)");
    await click(".o-voip-Keypad button:contains('1 other')");
    await contains(".o-voip-Keypad .o-voip-TabEntry-title:eq(0)", { text: "Adele" });
});

test("Keypad suggestion sorts recently-called contacts first", async () => {
    const pyEnv = await startServer();
    const colleenId = pyEnv["res.partner"].create({ name: "Colleen", phone: "+1-555-2001" });
    pyEnv["res.partner"].create({ name: "Cody", phone: "+1-555-2002" });
    pyEnv["voip.call"].create({
        phone_number: "+1-555-2001",
        partner_id: colleenId,
        user_id: serverState.userId,
        create_date: serializeDateTime(luxon.DateTime.now().minus({ days: 1 })),
    });

    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "co");
    await runAllTimers();

    await contains(".o-voip-Keypad button:contains('1 other')");
    await contains(".o-voip-Keypad button.btn-light:contains('Colleen')");
    await contains(".o-voip-Keypad button.btn-light:contains('Cody')", { count: 0 });
});

test("Keypad 'others' label show a meaningful and correct value", async () => {
    const pyEnv = await startServer();

    pyEnv["res.partner"].create(
        Array.from({ length: 31 }, (_, index) => ({
            name: `BBB Limit Contact ${String(index).padStart(2, "0")}`,
            phone: `+1-555-40${String(index).padStart(2, "0")}`,
        }))
    );

    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");

    await insertText(".o-voip-Keypad-input", "3");
    await runAllTimers();
    await contains(".o-voip-Keypad button:contains('3 others')"); // 03, 13, 23, 30 (- the suggestion)

    await insertText(".o-voip-Keypad-input", "Limit", { replace: true });
    await runAllTimers();
    await contains(".o-voip-Keypad button:contains('30 others')"); // There is exactly 31 records

    pyEnv["res.partner"].create({
        name: "BBB Limit Contact 31",
        phone: "+1-555-4031",
    });
    pyEnv["res.partner"].create({
        name: "AAA Limit Contact",
        phone: "+1-555-4031",
    });

    await insertText(".o-voip-Keypad-input", "BBB", { replace: true });
    await runAllTimers();
    await contains(".o-voip-Keypad button:contains('30+ others')"); // We know there is a 32nd record

    await insertText(".o-voip-Keypad-input", "Limit", { replace: true });
    await runAllTimers();
    await contains(".o-voip-Keypad button:contains('31+ others')"); // We already loaded by than 31 in the past
});

test("Keypad show more uses AddressBook with T9 search", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1234567890", t9_name: " 5646 363" },
        { name: "Joan Doe", phone: "+1987654321", t9_name: " 5626 363" },
        { name: "Bob Wilson", phone: "+1122334455", t9_name: " 262 94576" },
    ]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "56");
    await click(".o-voip-Keypad button:contains('1 other')");

    await contains(".o-voip-Keypad .o-voip-AddressBook");
    await contains(".o-voip-Keypad .o-voip-TabEntry-title", { text: "John Doe" });
    await contains(".o-voip-Keypad .o-voip-TabEntry:contains('John Doe')", {
        contains: [[".o-voip-highlighted-letter", { text: "Jo" }]],
    });
    await contains(".o-voip-Keypad .o-voip-TabEntry-title", { text: "Joan Doe" });
    await contains(".o-voip-Keypad .o-voip-TabEntry-title", { text: "Bob Wilson", count: 0 });
});

test.tags("focus required");
test("Entering and leaving keypad show more focuses the search input at the end", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1234567890" },
        { name: "Joan Doe", phone: "+1987654321" },
    ]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Jo");
    await contains(".o-voip-Keypad button:contains('1 other')");

    const keypadInput = queryOne(".o-voip-Keypad-input");
    keypadInput.setSelectionRange(0, 0);
    notifySelectionChange();
    await click(".o-voip-Keypad button:contains('1 other')");
    await contains(".o-voip-Keypad .o-voip-AddressBook .o-voip-Keypad-input:focus");

    const addressBookInput = queryOne(".o-voip-Keypad-input");
    expect(document.activeElement).toBe(addressBookInput);
    expect(addressBookInput.selectionStart).toBe(2);
    expect(addressBookInput.selectionEnd).toBe(2);

    addressBookInput.setSelectionRange(0, 0);
    notifySelectionChange();
    await click(".o-voip-Keypad-searchBar button[title='Back']");
    await contains(".o-voip-Keypad .o-voip-AddressBook", { count: 0 });
    await tick();

    const restoredKeypadInput = queryOne(".o-voip-Keypad-input");
    expect(document.activeElement).toBe(restoredKeypadInput);
    expect(restoredKeypadInput.selectionStart).toBe(2);
    expect(restoredKeypadInput.selectionEnd).toBe(2);
});

test("Keypad show more input can update the search term before going back", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1234567890", t9_name: " 5646 363" },
        { name: "Joan Doe", phone: "+1987654321", t9_name: " 5626 363" },
        { name: "Jane Doe", phone: "+1111111111", t9_name: " 5263 363" },
        { name: "Jack Doe", phone: "+2222222222", t9_name: " 5225 363" },
    ]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "56");
    await click(".o-voip-Keypad button:contains('1 other')");
    await contains(".o-voip-Keypad .o-voip-AddressBook");

    await insertText(".o-voip-Keypad-input", "526", { replace: true });
    await runAllTimers();

    await contains(".o-voip-Keypad .o-voip-AddressBook");
    await contains(".o-voip-Keypad .o-voip-TabEntry-title", { text: "Jane Doe" });
    await contains(".o-voip-Keypad .o-voip-TabEntry-title", { text: "Jack Doe", count: 0 });
    await contains(".o-voip-Keypad .o-voip-TabEntry-title", { text: "John Doe", count: 0 });
    await click(".o-voip-Keypad-searchBar button[title='Back']");
    await contains(".o-voip-Keypad .o-voip-AddressBook", { count: 0 });
    await contains(".o-voip-Keypad-searchBar input:value(526)");
});

test("Keypad show more refreshes recently-called contacts when editing the search", async () => {
    const pyEnv = await startServer();
    const colleenId = pyEnv["res.partner"].create({ name: "Colleen", phone: "+1-555-2001" });
    pyEnv["res.partner"].create({ name: "Cody", phone: "+1-555-2002" });
    const deniseId = pyEnv["res.partner"].create({ name: "Denise", phone: "+1-555-3001" });
    pyEnv["res.partner"].create({ name: "Derek", phone: "+1-555-3002" });
    const now = luxon.DateTime.now();
    pyEnv["voip.call"].create([
        {
            phone_number: "+1-555-2001",
            partner_id: colleenId,
            user_id: serverState.userId,
            create_date: serializeDateTime(now.minus({ days: 2 })),
        },
        {
            phone_number: "+1-555-3001",
            partner_id: deniseId,
            user_id: serverState.userId,
            create_date: serializeDateTime(now.minus({ days: 1 })),
        },
    ]);

    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "co");
    await click(".o-voip-Keypad button:contains('other')");
    await contains(".o-voip-Keypad .o-voip-AddressBook h2", { count: 0 });
    await contains(".o-voip-Keypad .o-voip-AddressBook .o-voip-TabEntry-title:eq(0)", {
        text: "Colleen",
    });
    let contactTitles = Array.from(
        document.querySelectorAll(".o-voip-Keypad .o-voip-AddressBook .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(contactTitles[0]).toBe("Colleen");
    await click(".o-voip-Keypad-searchBar button[title='Back']");

    await insertText(".o-voip-Keypad-input", "de", { replace: true });
    await click(".o-voip-Keypad button:contains('other')");
    await contains(".o-voip-Keypad .o-voip-AddressBook .o-voip-TabEntry-title:eq(0)", {
        text: "Denise",
    });
    contactTitles = Array.from(
        document.querySelectorAll(".o-voip-Keypad .o-voip-AddressBook .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(contactTitles[0]).toBe("Denise");

    await insertText(".o-voip-Keypad-input", "co", { replace: true });
    await runAllTimers();

    await contains(".o-voip-Keypad .o-voip-AddressBook h2", { count: 0 });
    await contains(".o-voip-Keypad .o-voip-AddressBook .o-voip-TabEntry-title:eq(0)", {
        text: "Colleen",
    });
    contactTitles = Array.from(
        document.querySelectorAll(".o-voip-Keypad .o-voip-AddressBook .o-voip-TabEntry-title"),
        (node) => node.textContent.trim()
    );
    expect(contactTitles[0]).toBe("Colleen");
});

test("Search by complete name works", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", complete_name: "Odoo, John Doe", phone: "+1234567890" },
        { name: "Jane Smith", complete_name: "Example, Jane Smith", phone: "+1987654321" },
        { name: "Bob Wilson", complete_name: "Bob Wilson", phone: "+1122334455" },
    ]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Jane");
    await contains(".o-voip-Keypad button:contains(Jane)");
    expect(".o-voip-Keypad button:contains(Jane)").toHaveText("Jane Smith +1987654321");

    await insertText(".o-voip-Keypad-input", "Odoo", { replace: true });
    await contains(".o-voip-Keypad button:contains(John)");
    expect(".o-voip-Keypad button:contains(John)").toHaveText("Odoo, John Doe +1234567890");
});

test("Keypad contact entry history action opens recent calls with that contact", async () => {
    const pyEnv = await startServer();
    const partnerAId = pyEnv["res.partner"].create({
        name: "Alice A",
        complete_name: "Alice A",
        phone: "+32498111111",
    });
    const partnerBId = pyEnv["res.partner"].create({
        name: "Alice B",
        complete_name: "Alice B",
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
    ]);
    onRpc("voip.call", "get_recent_phone_calls", (args) => {
        if (args.kwargs.partner_id === partnerAId) {
            expect.step("get_recent_phone_calls called with partner");
        }
    });

    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Alice");
    await runAllTimers();
    await click(".o-voip-Keypad button:contains('1 other')");
    await click(".o-voip-Keypad .o-voip-TabEntry:contains('Alice A')");
    await click(".o-voip-Keypad .o-voip-TabEntry:contains('Alice A') button[title='History']");

    expect.verifySteps(["get_recent_phone_calls called with partner"]);
    await contains("button[data-tab='recent'].active");
    await contains(".o-voip-History", { text: "Calls with Alice A" });
    await contains(".o-voip-History .o-voip-TabEntry:contains('Alice A')", { count: 1 });
    await contains(".o-voip-History .o-voip-TabEntry:contains('Alice B')", { count: 0 });
    await click(".o-voip-History button[title='Back']");
    await contains("button[data-tab='dialer'].active");
    await contains(".o-voip-Keypad .o-voip-TabEntry:contains('Alice A')");
});

test("Keypad suggestion IM status updates on bus notification without extra typing", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "admin",
        phone: "+1 555-555-5555",
        partner_share: false,
    });
    const userId = pyEnv["res.users"].create({ partner_id: partnerId, im_status: "online" });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "admi");
    await contains(".o-voip-Keypad button:contains(admin)");
    await contains(".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is online']");

    pyEnv["bus.bus"]._sendone(serverState.partnerId, "mail.record/insert", {
        "res.users": [
            {
                id: userId,
                im_status: "busy",
            },
        ],
    });
    await advanceTime(ImStatusMixin.IM_STATUS_DEBOUNCE_DELAY);
    await contains(".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is busy']");
});

test("Keypad suggestion shows phone IM status when user is on call and online", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Alice",
        phone: "+1 555-000-0001",
        partner_share: false,
    });
    pyEnv["res.users"].create({
        login: "alice_voip",
        partner_id: partnerId,
        im_status: "online",
        should_display_in_call_im_status: true,
    });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Ali");
    await contains(".o-voip-Keypad button:contains(Alice)");
    await contains(
        ".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is on a call and online']"
    );
});

test("Keypad suggestion updates to phone IM status when active call changes from bus", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Alice",
        phone: "+1 555-000-0001",
        partner_share: false,
    });
    const userId = pyEnv["res.users"].create({
        login: "alice_voip",
        partner_id: partnerId,
        im_status: "online",
        should_display_in_call_im_status: false,
    });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Ali");
    await contains(".o-voip-Keypad button:contains(Alice)");
    await contains(".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is online']");
    await contains(
        ".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is on a call and online']",
        {
            count: 0,
        }
    );

    pyEnv["bus.bus"]._sendone(serverState.partnerId, "mail.record/insert", {
        "res.users": [{ id: userId, should_display_in_call_im_status: true }],
    });
    await tick();
    await contains(
        ".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is on a call and online']"
    );
});

test("Keypad suggestion does not show phone IM status when user is offline", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Bob",
        phone: "+1 555-000-0002",
        partner_share: false,
    });
    pyEnv["res.users"].create({
        login: "bob_voip",
        partner_id: partnerId,
        im_status: "offline",
        should_display_in_call_im_status: true,
    });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Bob");
    await contains(".o-voip-Keypad button:contains(Bob)");
    await contains(".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is offline']");
});

test("Contact search restores phone IM status after manual offline then online", async () => {
    const pyEnv = await startServer();
    const partnerId = pyEnv["res.partner"].create({
        name: "Demo",
        phone: "+1 555-000-0003",
        partner_share: false,
    });
    const userId = pyEnv["res.users"].create({
        login: "demo_voip",
        partner_id: partnerId,
        im_status: "online",
        should_display_in_call_im_status: true,
    });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "Demo");
    await contains(".o-voip-Keypad button:contains(Demo)");
    await contains(
        ".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is on a call and online']"
    );

    const offlineStatusData = {
        im_status: "offline",
        should_display_in_call_im_status: false,
    };
    pyEnv["res.users"].write(userId, offlineStatusData);
    pyEnv["bus.bus"]._sendone(serverState.partnerId, "mail.record/insert", {
        "res.users": [{ id: userId, ...offlineStatusData }],
    });
    await advanceTime(ImStatusMixin.IM_STATUS_DEBOUNCE_DELAY);
    await contains(".o-voip-Keypad button.btn-light .o-mail-ImStatus[title='User is offline']");

    await click("button[data-tab='recent']");
    await runAllTimers();
    await insertText("input[id='o-voip-Tab-searchInput']", "Demo");
    await runAllTimers();
    await contains(".o-voip-TabEntry:contains(Demo) .o-mail-ImStatus[title='User is offline']");

    const onlineStatusData = {
        im_status: "online",
        should_display_in_call_im_status: true,
    };
    pyEnv["res.users"].write(userId, onlineStatusData);
    pyEnv["bus.bus"]._sendone(serverState.partnerId, "mail.record/insert", {
        "res.users": [{ id: userId, ...onlineStatusData }],
    });
    await tick();
    await contains(
        ".o-voip-TabEntry:contains(Demo) .o-mail-ImStatus[title='User is on a call and online']"
    );
});

test("Search by phone number works", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1234567890" },
        { name: "Jane Smith", phone: "+1987654321" },
        { name: "Bob Wilson", phone: "+1122334455" },
    ]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "123456");
    await contains(".o-voip-Keypad button:contains(123456)");
});

test("Search by phone number falls back to phone_formatted", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create({
        name: "John Doe",
        phone: "1234567890",
        phone_sanitized: "+11234567890",
        phone_formatted: "+1 123 456 7890",
    });
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click(".o-voip-Softphone nav button:contains(Keypad)");
    // Search term has country code prefix that doesn't match raw `phone`,
    // but should match `phone_formatted` via fallback.
    await insertText(".o-voip-Keypad-input", "+11234567890");
    await contains(".o-voip-Keypad button:contains(John Doe)");
    await contains(".o-voip-Keypad button:contains(+1 123 456 7890)");
});

test("T9 search does not match when contact has falsy t9_name", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([{ name: " ", phone: "+1234567890", t9_name: false }]);
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input", "456");
    await contains(".o-voip-Keypad button:contains(+1234567890)");
    await edit("66");
    await contains(".o-voip-Keypad .d-flex.flex-column.mx-3", { count: 0 });
});

test("Using up/down arrows to browse keypad search suggestion", async () => {
    const pyEnv = await startServer();
    pyEnv["res.partner"].create([
        { name: "John Doe", phone: "+1234567890" },
        { name: "Jane Smith", phone: "+1234560000" },
    ]);
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");

    await insertText(".o-voip-Keypad-searchBar input", "123");
    const inputEl = queryOne(".o-voip-Keypad-searchBar input");
    expect(document.activeElement).toBe(inputEl);
    await contains(".o-voip-highlighted-letter:text(123)"); // Wait for suggestions to appear
    await press("ArrowDown");
    expect(document.activeElement).toHaveClass("btn-light");
    // Jane Smith is first because the default sort is ID *desc*
    expect(document.activeElement).toHaveText("Jane Smith +1234560000");
    await press("ArrowDown");
    expect(document.activeElement).toHaveClass("btn-link"); // Show more button
    await press("ArrowDown");
    expect(document.activeElement).toHaveClass("btn-link"); // Nothing below so nothing changed
    await press("ArrowUp");
    expect(document.activeElement).toHaveClass("btn-light");
    expect(document.activeElement).toHaveText("Jane Smith +1234560000");
    await press("ArrowUp");
    expect(document.activeElement).toBe(inputEl);

    await insertText(".o-voip-Keypad-searchBar input", "4567");
    inputEl.selectionStart = inputEl.selectionEnd = 3;
    await contains(".o-voip-highlighted-letter:text(1234567)"); // Wait for suggestions to appear
    await press("ArrowDown");
    expect(document.activeElement).toBe(inputEl);
    expect(inputEl.selectionStart).toBe(7);
    expect(inputEl.selectionEnd).toBe(7);
    await press("ArrowDown");
    expect(document.activeElement).toHaveClass("btn-light");
    expect(document.activeElement).toHaveText("John Doe +1234567890");
    await press("ArrowDown");
    expect(document.activeElement).toHaveClass("btn-light");
    expect(document.activeElement).toHaveText("John Doe +1234567890"); // No other result so nothing changed
    await press("ArrowUp");
    expect(document.activeElement).toBe(inputEl);
    expect(inputEl.selectionStart).toBe(7);
    expect(inputEl.selectionEnd).toBe(7);
    await press("ArrowUp");
    expect(document.activeElement).toBe(inputEl);
    expect(inputEl.selectionStart).toBe(0);
    expect(inputEl.selectionEnd).toBe(0);
});

test("Long pressing on '0' should insert '+'", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar input");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    const el = queryFirst(".o-voip-Keypad-digit:contains(0)");
    el.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
    await advanceTime(500);
    el.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    expect(input.selectionStart).toBe(1);
    expect(input.selectionEnd).toBe(1);
    await contains(".o-voip-Keypad-searchBar input:value(+)");
});

test("Right-clicking on a key does not trigger long press actions", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-digitBtn:has(span:text('5'))");
    const el = queryFirst(".o-voip-Keypad-digit:text(5)");
    el.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, button: 2 }));
    await advanceTime(9999);
    await click(".o-voip-Keypad-digitBtn:has(span:text('2'))");
    await contains(".o-voip-Keypad-searchBar input:value(/^2$/)");
});

test.tags("focus required");
test("Selection starting at the beginning is removed when clicking Backspace.", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "0123456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(0, 2);
    notifySelectionChange();
    await click(".o-voip-Keypad-searchBar button[title=Backspace]");
    expect(input.selectionStart).toBe(0);
    expect(input.selectionEnd).toBe(0);
    await contains(".o-voip-Keypad-searchBar input:value(23456)");
});

test("When provider has no voicemail code configured, no voicemail icon will be shown on key '1'", async () => {
    const pyEnv = await startServer();
    const [defaultProviderId] = pyEnv["voip.provider"].search([["name", "=", "Default"]]);
    pyEnv["voip.provider"].write(defaultProviderId, { voicemail_code: "" });
    pyEnv["res.users"].write(serverState.userId, { voip_provider_id: defaultProviderId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-digitBtn span:text('1')");
    await contains(
        ".o-voip-Keypad-digitBtn:has(span:text('1')):has(span.o-voip-Keypad-voicemail)",
        { count: 0 }
    );
});

test("When provider has voicemail code configured, a voicemail icon will be shown on key '1', long press that key will call the voicemail", async () => {
    const pyEnv = await startServer();
    const [defaultProviderId] = pyEnv["voip.provider"].search([["name", "=", "Default"]]);
    pyEnv["voip.provider"].write(defaultProviderId, { voicemail_code: "*98" });
    pyEnv["res.users"].write(serverState.userId, { voip_provider_id: defaultProviderId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-digitBtn:has(span:text('1')):has(span.o-voip-Keypad-voicemail)");
    const el = queryFirst(".o-voip-Keypad-digit:text(1)");
    el.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
    await advanceTime(500);
    el.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await contains(".o-voip-ContactInfo:text('Mailbox')");
    expect(pyEnv["voip.call"].search_count([["phone_number", "=", "*98"]])).toBe(1);
});

test("No voicemail icon will be shown on in-call view keypad", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "123456");
    await click("button[title='Call']");
    runAllTimers();
    await contains(".o-voip-InCallView-pad button[title='Keypad']:enabled");
    await click(".o-voip-InCallView-pad button[title='Keypad']");
    await contains(".o-voip-Keypad-digitBtn span:text('1')");
    await contains(
        ".o-voip-Keypad-digitBtn:has(span:text('1')):has(span.o-voip-Keypad-voicemail)",
        { count: 0 }
    );
});

test("No voicemail icon will be shown on transfer keypad", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-input", "123456");
    await click("button[title='Call']");
    await tick();
    runAllTimers();
    await contains(".o-voip-InCallView-pad button[title='Transfer']:enabled");
    await click(".o-voip-InCallView-pad button[title='Transfer']");
    await contains("button.active[title='Contacts']");
    await click(".o-voip-InCallView-pad button[title='Keypad']");
    await contains(".o-voip-Keypad-digitBtn span:text('1')");
    await contains(
        ".o-voip-Keypad-digitBtn:has(span:text('1')):has(span.o-voip-Keypad-voicemail)",
        { count: 0 }
    );
});

test("When calling a mailbox, `Mailbox` is shown instead of its code", async () => {
    const pyEnv = await startServer();
    const [defaultProviderId] = pyEnv["voip.provider"].search([["name", "=", "Default"]]);
    pyEnv["voip.provider"].write(defaultProviderId, { voicemail_code: "*98" });
    pyEnv["res.users"].write(serverState.userId, { voip_provider_id: defaultProviderId });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad");
    const el = queryFirst(".o-voip-Keypad-digit:text(1)");
    el.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
    await advanceTime(500);
    el.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await contains(".o-voip-ContactInfo:text('Mailbox')");
    runAllTimers();
    await contains(".o-voip-InCallView-pad button[title='Add Call']:enabled");
    await click(".o-voip-InCallView-pad button[title='Add Call']");
    await contains("button.active[title='Contacts']");
    await click(".o-voip-InCallView-pad button[title='Keypad']");
    await insertText(".o-voip-Keypad-input", "123456");
    await click("button[title='Call']");
    await contains(".o-voip-CallBanner span:text('Mailbox')");
    await click(".o-voip-InCallView-pad button[title='Hang up']");
    await click(".o-voip-InCallView-pad button[title='Hang up']");
    await contains(".o-voip-CallSummary p:text('Mailbox')");
});

test("initial country falls back to user's company country when last call has no country", async () => {
    const pyEnv = await startServer();
    const beCountry = {
        code: "BE",
        name: "Belgium",
        phone_code: 32,
        image_url: "/base/static/img/country_flags/be.png",
    };
    // create() fills the record with every default: keep the fixture for the insert below
    const beId = pyEnv["res.country"].create({ ...beCountry });
    serverState.companies = [{ ...serverState.companies[0], country_id: beId }];
    pyEnv["voip.call"].create({
        phone_number: "12345",
        state: "terminated",
        user_id: serverState.userId,
    });
    await start();
    getService("mail.store").insert({
        "res.country": [{ id: beId, ...beCountry, phone_code: String(beCountry.phone_code) }],
    });
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar button[title='Belgium']");
});

test("initial country is taken from last call when it has a country_id", async () => {
    const pyEnv = await startServer();
    const beCountry = {
        code: "BE",
        name: "Belgium",
        phone_code: 32,
        image_url: "/base/static/img/country_flags/be.png",
    };
    const cnCountry = {
        code: "CN",
        name: "China",
        phone_code: 86,
        image_url: "/base/static/img/country_flags/cn.png",
    };
    // create() fills the record with every default: keep the fixture for the insert below
    const beId = pyEnv["res.country"].create({ ...beCountry });
    const cnId = pyEnv["res.country"].create({ ...cnCountry });
    serverState.companies = [{ ...serverState.companies[0], country_id: beId }];
    pyEnv["voip.call"].create({
        phone_number: "+861234567890",
        state: "terminated",
        user_id: serverState.userId,
        country_id: cnId,
    });
    await start();
    getService("mail.store").insert({
        "res.country": [
            { id: beId, ...beCountry, phone_code: String(beCountry.phone_code) },
            { id: cnId, ...cnCountry, phone_code: String(cnCountry.phone_code) },
        ],
    });
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar button[title='China']");
});
