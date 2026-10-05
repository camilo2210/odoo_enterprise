import { expect, test } from "@odoo/hoot";
import { click, contains, patchUiSize, start, startServer } from "@mail/../tests/mail_test_helpers";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { patchWithCleanup, serverState } from "@web/../tests/web_test_helpers";
import { Voip } from "@voip/core/web/voip_service";

setupVoipTests();

test("Clicking on systray item when softphone is hidden shows the softphone.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains(".o-voip-Softphone");
});

test("Clicking on systray item when softphone is displayed hides the softphone.", async () => {
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await click(".o_menu_systray button[title='Hide Softphone']");
    await contains(".o-voip-Softphone");
});

test("Display missed call count in systray rounded pill “10” when there are 10 missed calls", async () => {
    const pyEnv = await startServer();
    for (let i = 0; i < 10; ++i) {
        pyEnv["voip.call"].create({ state: "missed", user_id: serverState.userId });
    }
    await start();
    await contains("button[title='Show Softphone']", { text: "10" });
});

test("Clicking on VoIP systray button with missed calls opens the softphone on recent tab", async () => {
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        state: "missed",
        user_id: serverState.userId,
        phone_number: "+494066969669",
    });
    await start();
    await click(".o_menu_systray button[title='Show Softphone']");
    await contains("button[data-tab='recent'].active");
    await contains(".o-voip-TabEntry", { text: "+494066969669" });
});

test.tags("mobile");
test("VoIP systray button should be hidden when this is not configured for the current user", async () => {
    patchWithCleanup(Voip.prototype, {
        get canCall() {
            return false;
        },
    });
    await patchUiSize({ width: 500 });
    await start();
    expect(".o_menu_systray button[title='Show Softphone']").toHaveClass("d-none");
});

test.tags("mobile");
test("VoIP systray button should be displayed when this is configured for the current user", async () => {
    await patchUiSize({ width: 500 });
    await start();
    expect(".o_menu_systray button[title='Show Softphone']").not.toHaveClass("d-none");
});
