import { describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { mountWithCleanup, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { ClickbotLauncher, SUCCESS_SIGNAL } from "@web/webclient/clickbot/clickbot";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop").timeout(10000);

defineStudioEnvironment();

test("clickbot clickeverywhere test", async () => {
    const { promise, resolve } = Promise.withResolvers();

    onRpc("grid_unavailability", () => ({}));

    patchWithCleanup(console, {
        log: (msg) => {
            expect.step(msg);
            if (msg === SUCCESS_SIGNAL) {
                resolve();
            }
        },
        error: (msg) => {
            expect.step(msg);
            resolve();
        },
    });

    const webClient = await mountWithCleanup(WebClientEnterprise);
    patchWithCleanup(odoo, {
        info: {
            isEnterprise: 1,
        },
        __WOWL_DEBUG__: { root: webClient },
    });
    patchWithCleanup(performance, {
        now: () => 43554.39999999106,
    });

    await animationFrame();

    new ClickbotLauncher(webClient.env, { logger: true }).start();
    await promise;
    expect.verifySteps([
        "Starting ClickEverywhere test",
        "Testing app: Partners 1 (app_1)",
        "Testing menu Partners 11 (menu_11)",
        "Clicking on: kanban view's new button",
        "Clicking on: go back to kanban view (from new record form view)",
        "Clicking on: open form view from kanban",
        "Clicking on: go back to kanban view (from record view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing view switch: list",
        "Clicking on: list view switcher",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing view switch: grid",
        "Clicking on: grid view switcher",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing view switch: pivot",
        "Clicking on: pivot view switcher",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing menu Partners 12 (menu_12)",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Clicking on: open form view from list",
        "Clicking on: go back to list view (from record view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing view switch: kanban",
        "Clicking on: kanban view switcher",
        "Clicking on: kanban view's new button",
        "Clicking on: go back to kanban view (from new record form view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing view switch: grid",
        "Clicking on: grid view switcher",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing app: Ponies (app_2)",
        "Testing menu Ponies (app_2)",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Clicking on: open form view from list",
        "Clicking on: go back to list view (from record view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 1 filters",
        'Clicking on: filter "apple"',
        "Testing app: Dogs (app_3)",
        "Testing menu Dogs (app_3)",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing view switch: kanban",
        "Clicking on: kanban view switcher",
        "Clicking on: kanban view's new button",
        "Clicking on: go back to kanban view (from new record form view)",
        "Clicking on: entering studio",
        "Clicking on: leaving studio",
        "Testing 0 filters",
        "Testing app: Settings (app_4)",
        "Testing menu Settings (app_4)",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Testing 0 filters",
        "Test took 0 seconds",
        "Tested 4 apps",
        "Tested 5 menus",
        "Tested 11 views",
        "Tested 3 form views",
        "Tested 8 new record views",
        "Tested 0 modals",
        "Tested 1 filters",
        "Tested 10 views in Studio",
        SUCCESS_SIGNAL,
    ]);
});
