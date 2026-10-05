import { describe, expect, test } from "@odoo/hoot";
import { click, contains, start, startServer } from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { highlightMatch } from "@voip/utils/highlight";
import { serverState } from "@web/../tests/web_test_helpers";

describe.current.tags("headless");
setupVoipTests();

test("highlightMatch", () => {
    const match = highlightMatch("Œdipe Roi", "oed");
    expect(match.valueOf()).toBe(
        `<span class="o-voip-highlighted-letter fw-bolder">Œd</span>ipe Roi`
    );
});

test("Show last called number when click on call button with empty input", async () => {
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        direction: "outgoing",
        phone_number: "001",
        state: "terminated",
        create_date: "2012-09-25 00:00:00",
        user_id: serverState.userId,
    });
    pyEnv["voip.call"].create({
        direction: "outgoing",
        phone_number: "002",
        state: "terminated",
        create_date: "2019-12-17 00:00:00",
        user_id: serverState.userId,
    });
    pyEnv["voip.call"].create({
        direction: "incoming",
        phone_number: "003",
        state: "terminated",
        create_date: "2025-11-05 00:00:00",
        user_id: serverState.userId,
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click("button[data-tab='dialer']");
    await contains(".o-voip-Keypad-searchBar input:empty");
    await click("button[title='Call']");
    await contains(".o-voip-Keypad-searchBar input:value(002)");
});
