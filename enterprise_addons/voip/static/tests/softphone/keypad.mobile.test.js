import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, contains, insertText, start } from "@mail/../tests/mail_test_helpers";
import { getService } from "@web/../tests/web_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

import { mockUserAgent } from "@odoo/hoot-mock";

describe.current.tags("mobile");
setupVoipTests();

// Force Owl to instantiate the keypad in mobile mode for these tests only.
beforeEach(() => mockUserAgent("android"));

function notifySelectionChange() {
    document.dispatchEvent(new Event("selectionchange"));
}

test.tags("focus required");
test("mobile backspace button deletes keyboard-selected characters", async () => {
    await start();
    const voipService = await getService("voip");
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar input:focus");
    await insertText(".o-voip-Keypad-searchBar input:focus", "223456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(1, 4);
    // manually notify useSelection that the selection changed programmatically
    notifySelectionChange();
    input.blur();
    await click(".o-voip-Keypad-searchBar button[title=Backspace]");
    await contains(".o-voip-Keypad-searchBar input[data-value='256']");
    expect(voipService.softphone.dialer.input.selection.start).toBe(1);
    expect(voipService.softphone.dialer.input.selection.end).toBe(1);
});

test.tags("focus required");
test("mobile country selector filter input is auto-focused when opening dropdown", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await click(".o-voip-Keypad-searchBar .o-voip-countryFlag");
    await contains(".o-voip-countryDropdown-search input:focus");
});

test.tags("focus required");
test("mobile keypad digits respect keyboard selection after blur", async () => {
    await start();
    const voipService = await getService("voip");
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar input:focus");
    await insertText(".o-voip-Keypad-searchBar input:focus", "023456");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    input.setSelectionRange(2, 4);
    notifySelectionChange();
    input.blur();
    await click(".o-voip-Keypad-digit:contains(9)");
    await contains(".o-voip-Keypad-searchBar input[data-value='02956']");
    expect(voipService.softphone.dialer.input.selection.start).toBe(3);
    expect(voipService.softphone.dialer.input.selection.end).toBe(3);
});

test.tags("focus required");
test("mobile keypad digits honor cursor position after keypad input", async () => {
    await start();
    await click(".o_menu_systray [title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await click(".o-voip-Keypad-searchBar input");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    await insertText(".o-voip-Keypad-searchBar input:focus", "1234");
    await contains(".o-voip-Keypad-searchBar input[data-value='1234']");
    input.focus();
    input.setSelectionRange(0, 0);
    notifySelectionChange();
    for (const digit of "987") {
        await click(`.o-voip-Keypad-digit:contains(${digit})`);
    }
    await contains(".o-voip-Keypad-searchBar input[data-value='9871234']");
});

test.tags("focus required");
test("Clicking a keypad key *should* focus the input on mobile, to see the cursor", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");
    await click(".o-voip-Keypad-digitBtn:has(> span:text('2'))");
    const input = document.querySelector(".o-voip-Keypad-searchBar input");
    expect(document.activeElement).toBe(input);
});

test.tags("focus required");
test("Cursor position is correct after backspace in the middle of a number", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "123456");
    const inputEl = document.querySelector(".o-voip-Keypad-searchBar input");
    inputEl.setSelectionRange(3, 3);

    // TODO this would not be needed if `useSelection.moveCursor` would actually
    // move the cursor in mobile also... or at least this was the case before
    // 19.1, it does not seem to be the case anymore. Also, other tests manually
    // trigger a selectionchange, which is not really good and does not seem to
    // work here. Something to investigate. The "user" flow is working either
    // way, as there always be a small delay between each keystroke.
    // See SELECTION_CHANGE_PROBLEM.
    await new Promise(setTimeout);

    await click(".o-voip-Keypad-backspace");
    await contains(".o-voip-Keypad-searchBar input:value(12456)");
    expect(inputEl.selectionStart).toBe(2);
    expect(inputEl.selectionEnd).toBe(2);
});

test.tags("focus required");
test("Cursor position is correct after inserting a number in the middle of a number", async () => {
    await start();
    await click(".o_menu_systray button:has(> [data-icon='phone'].oi-filled)");
    await click("button[data-tab='dialer']");
    await insertText(".o-voip-Keypad-searchBar input:focus", "123456");
    const inputEl = document.querySelector(".o-voip-Keypad-searchBar input");
    inputEl.setSelectionRange(3, 3);

    // TODO See SELECTION_CHANGE_PROBLEM.
    await new Promise(setTimeout);

    await click(".o-voip-Keypad-digitBtn:has(> span:text('8'))");
    await contains(".o-voip-Keypad-searchBar input:value(1238456)");
    expect(inputEl.selectionStart).toBe(4);
    expect(inputEl.selectionEnd).toBe(4);
});
