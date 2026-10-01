import {
    advanceTime,
    animationFrame,
    click,
    drag,
    expect,
    mockDate,
    mockTouch,
    pointerDown,
    press,
    queryFirst,
    queryRect,
    test,
} from "@odoo/hoot";
import {
    contains,
    defineMenus,
    getService,
    mockOffline,
    mockService,
    mountWebClient,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { OfflinePlugin } from "@web/core/offline/offline_plugin";
import { registry } from "@web/core/registry";
import { range } from "@web/core/utils/numbers";
import { session } from "@web/session";
import { reorderApps } from "@web/webclient/menus/menu_helpers";
import { ShareTargetItem } from "@web/webclient/share_target/share_target_item";
import { shareTargetService } from "@web/webclient/share_target/share_target_service";
import { HomeMenu } from "@web_enterprise/webclient/home_menu/home_menu";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";

/**
 * @param {Iterable<{
 *  index?: number;
 *  key: import("@odoo/hoot").KeyStrokes;
 *  shiftKey?: boolean;
 * }>} steps
 */
async function walkOn(steps) {
    for (const step of steps) {
        await press(step.key);
        await animationFrame();
        expect(`.o_menuitem:eq(${step.index || 0})`).toHaveClass("o_focused", {
            message: `step ${JSON.stringify(step)}`,
        });
    }
}

const getDefaultHomeMenuProps = () => {
    const apps = [
        {
            actionID: 121,
            href: "/odoo/action-121",
            appID: 1,
            id: 1,
            label: "Discuss",
            parents: "",
            webIcon: false,
            xmlid: "app.1",
        },
        {
            actionID: 122,
            href: "/odoo/action-122",
            appID: 2,
            id: 2,
            label: "Calendar",
            parents: "",
            webIcon: false,
            xmlid: "app.2",
        },
        {
            actionID: 123,
            href: "/odoo/contacts",
            appID: 3,
            id: 3,
            label: "Contacts",
            parents: "",
            webIcon: false,
            xmlid: "app.3",
        },
    ];
    return { apps, reorderApps: (order) => reorderApps(apps, order) };
};

test.tags("desktop");
test("ESC Support", async () => {
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    mockService("home_menu", {
        async toggle(show) {
            expect.step(`toggle ${show}`);
        },
    });
    await press("escape");
    expect.verifySteps(["toggle false"]);
});

test("Click on an app", async () => {
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    mockService("menu", {
        async selectMenu(menu) {
            expect.step(`selectMenu ${menu.id}`);
        },
    });
    await click(".o_menuitem:eq(0)");
    await animationFrame();
    expect.verifySteps(["selectMenu 1"]);
});

test("Display Expiration Panel (no module installed)", async () => {
    mockDate("2019-10-09T00:00:00");

    patchWithCleanup(session, {
        expiration_date: "2019-11-01 12:00:00",
        expiration_reason: "",
        isMailInstalled: false,
        warning: "admin",
    });

    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });

    expect(".database_expiration_panel").toHaveCount(1);
    expect(".database_expiration_panel .oe_instance_register").toHaveText(
        "You will be able to register your database once you have installed your first app.",
        { message: "There should be an expiration panel displayed" }
    );

    // Close the expiration panel
    await click(".database_expiration_panel .oe_instance_hide_panel");
    await animationFrame();
    expect(".database_expiration_panel").toHaveCount(0);
});

test.tags("desktop");
test("Navigation (only apps, only one line)", async () => {
    expect.assertions(8);

    const homeMenuProps = {
        apps: range(3).map((i) => ({
            actionID: 120 + i,
            href: "/odoo/act" + (120 + i),
            appID: i + 1,
            id: i + 1,
            label: `0${i}`,
            parents: "",
            webIcon: false,
            xmlid: `app.${i}`,
        })),
        reorderApps: (order) => reorderApps(homeMenuProps.apps, order),
    };
    await mountWithCleanup(HomeMenu, {
        props: homeMenuProps,
    });

    await walkOn([
        { key: "ArrowDown", index: 0 },
        { key: "ArrowRight", index: 1 },
        { key: "Tab", index: 2 },
        { key: "ArrowRight", index: 0 },
        { key: ["Shift", "Tab"], index: 2 },
        { key: "ArrowLeft", index: 1 },
        { key: "ArrowDown", index: 1 },
        { key: "ArrowUp", index: 1 },
    ]);
});

test.tags("desktop");
test("Navigation (only apps, two lines, one incomplete)", async () => {
    expect.assertions(19);

    const homeMenuProps = {
        apps: range(8).map((i) => ({
            actionID: 121,
            href: "/odoo/action-121",
            appID: i + 1,
            id: i + 1,
            label: `0${i}`,
            parents: "",
            webIcon: false,
            xmlid: `app.${i}`,
        })),
        reorderApps: (order) => reorderApps(homeMenuProps.apps, order),
    };
    await mountWithCleanup(HomeMenu, {
        props: homeMenuProps,
    });

    await walkOn([
        { key: "ArrowRight", index: 0 },
        { key: "ArrowUp", index: 6 },
        { key: "ArrowUp", index: 0 },
        { key: "ArrowDown", index: 6 },
        { key: "ArrowDown", index: 0 },
        { key: "ArrowRight", index: 1 },
        { key: "ArrowRight", index: 2 },
        { key: "ArrowUp", index: 7 },
        { key: "ArrowUp", index: 1 },
        { key: "ArrowRight", index: 2 },
        { key: "ArrowDown", index: 7 },
        { key: "ArrowDown", index: 1 },
        { key: "ArrowUp", index: 7 },
        { key: "ArrowRight", index: 6 },
        { key: "ArrowLeft", index: 7 },
        { key: "ArrowUp", index: 1 },
        { key: "ArrowLeft", index: 0 },
        { key: "ArrowLeft", index: 5 },
        { key: "ArrowRight", index: 0 },
    ]);
});

test.tags("desktop");
test("Navigation and open an app in the home menu", async () => {
    expect.assertions(6);

    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    mockService("menu", {
        async selectMenu(menu) {
            expect.step(`selectMenu ${menu.id}`);
        },
    });
    // No app selected so nothing to open
    await press("enter");
    expect.verifySteps([]);

    await walkOn([
        { key: "ArrowDown", index: 0 },
        { key: "ArrowRight", index: 1 },
        { key: "Tab", index: 2 },
        { key: "shift+Tab", index: 1 },
    ]);

    // open first app (Calendar)
    await press("enter");

    expect.verifySteps(["selectMenu 2"]);
});

test("Reorder apps in home menu using drag and drop", async () => {
    const apps = [];
    for (let i = 0; i < 8; i++) {
        apps.push({
            actionID: 121,
            href: "/odoo/action-121",
            appID: i + 1,
            id: i + 1,
            label: `0${i}`,
            parents: "",
            webIcon: false,
            xmlid: `app.${i}`,
        });
    }
    defineMenus(apps);

    onRpc("set_res_users_settings", () => {
        expect.step(`set_res_users_settings`);
        return {
            id: 1,
            homemenu_config: '["app.1","app.2","app.3","app.0","app.4","app.5","app.6","app.7"]',
        };
    });
    await mountWebClient({ WebClient: WebClientEnterprise });
    const { moveTo, drop } = await drag(".o_draggable:first-child");
    await advanceTime(250);
    expect(".o_draggable:first-child a").not.toHaveClass("o_dragged_app");
    await advanceTime(250);
    expect(".o_draggable:first-child a").toHaveClass("o_dragged_app");
    await moveTo(".o_draggable:first-child", {
        position: {
            x: 70,
            y: 35,
        },
        relative: true,
    });
    await drop(".o_draggable:not(.o_dragged):eq(3)");
    await animationFrame();
    expect.verifySteps(["set_res_users_settings"]);
    expect(".o_app:eq(0)").toHaveAttribute("data-menu-xmlid", "app.1", {
        message: "first displayed app has app.1 xmlid",
    });
    expect(".o_app:eq(3)").toHaveAttribute("data-menu-xmlid", "app.0", {
        message: "app 0 is now at 4th position",
    });
});

test.tags("desktop");
test("The HomeMenu input takes the focus when you press a key only if no other element is the activeElement", async () => {
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    expect(".o_home_menu_search_input").toBeFocused();

    const activeElement = document.createElement("div");
    getService("ui").activateElement(activeElement);
    // remove the focus from the input
    const otherInput = document.createElement("input");
    queryFirst(".o_home_menu").appendChild(otherInput);
    await pointerDown(otherInput);
    await pointerDown(document.body);
    expect(document.body).toBeFocused();
    expect(".o_command_palette_search input").not.toHaveCount();

    await press("a");
    await animationFrame();
    expect(document.body).toBeFocused();
    expect(".o_command_palette_search input").not.toHaveCount();

    getService("ui").deactivateElement(activeElement);
    await press("a");
    await animationFrame();
    expect(".o_command_palette_search input").toBeFocused();
});

test.tags("desktop");
test("The HomeMenu input does not take the focus if it is already on another input", async () => {
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    expect(".o_home_menu_search_input").toBeFocused();

    const otherInput = document.createElement("input");
    queryFirst(".o_home_menu").appendChild(otherInput);
    await pointerDown(otherInput);
    await press("a");
    await animationFrame();
    expect(otherInput).toBeFocused();
    expect(".o_command_palette_search input").not.toHaveCount();

    otherInput.remove();
    await press("a");
    await animationFrame();
    expect(".o_command_palette_search input").toBeFocused();
});

test.tags("desktop");
test("The HomeMenu input does not take the focus if it is already on a textarea", async () => {
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    expect(".o_home_menu_search_input").toBeFocused();

    const textarea = document.createElement("textarea");
    queryFirst(".o_home_menu").appendChild(textarea);
    await pointerDown(textarea);
    await press("a");
    await animationFrame();
    expect(textarea).toBeFocused();
    expect(".o_command_palette_search input").not.toHaveCount();

    textarea.remove();
    await press("a");
    await animationFrame();
    expect(".o_command_palette_search input").toBeFocused();
});

test("home search input on touch devices", async () => {
    mockTouch(true);
    document.body.classList.add("o_touch_device");
    const apps = [];
    for (let i = 0; i < 8; i++) {
        apps.push({
            actionID: 121,
            href: "/odoo/action-121",
            appID: i + 1,
            id: i + 1,
            label: `0${i}`,
            parents: "",
            webIcon: false,
            xmlid: `app.${i}`,
        });
    }
    defineMenus(apps);
    await mountWebClient({ WebClient: WebClientEnterprise });
    expect(".o_home_menu_search_input").not.toBeFocused({
        message: "home menu search input shouldn't have the focus",
    });
    const navbarHeight = queryRect(".o_navbar").height;
    expect(".o_home_menu").toHaveProperty("scrollTop", navbarHeight, {
        message:
            "home menu scrolls to the apps container initially (to hide the search input behind the navbar)",
    });
    await contains(".o_home_menu").scroll({ top: 0 });
    await contains(".o_home_menu_search_input").click();
    expect(".o_command_palette").toHaveCount(1, {
        message: "command palette should open on search input click on touch devices",
    });
    expect(".o_command_palette_listbox").toHaveText(
        "App1\nApp2\nApp3\nApp4\nApp5\nApp6\nApp7\nApp8",
        {
            message: "apps are listed in the command palette",
        }
    );
});

test.tags("desktop");
test("home keynav not triggering when navigating a dropdown", async () => {
    const apps = [];
    for (let i = 0; i < 8; i++) {
        apps.push({
            actionID: 121,
            href: "/odoo/action-121",
            appID: i + 1,
            id: i + 1,
            label: `0${i}`,
            parents: "",
            webIcon: false,
            xmlid: `app.${i}`,
        });
    }
    defineMenus(apps);

    await mountWebClient({ WebClient: WebClientEnterprise });

    await click(".o_user_menu");
    await animationFrame();

    await press("arrowdown");
    await animationFrame();
    expect(".o-dropdown-item.focus").toHaveCount(1);

    await press("arrowleft");
    await animationFrame();
    expect(".o-dropdown-item.focus").toHaveCount(1);
    expect(".o_app.o_focused").toHaveCount(0);
});

test.tags("desktop");
test("Drop file on HomeMenu should trigger the share target dialog if having share target items", async () => {
    registry.category("share_target_items").add("fake_share_target", ShareTargetItem);
    const files = [new File([new Uint8Array(1)], "text.png", { type: "image/png" })];
    patchWithCleanup(shareTargetService, {
        _displayShareTarget() {
            expect.step("display_share_target");
        },
    });
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    const { moveTo, drop } = await drag(".o-main-components-container", { files });
    await moveTo(".o_home_menu");
    await animationFrame();
    await drop(".o-Dropzone");
    await animationFrame();
    expect.verifySteps(["display_share_target"]);
});

test.tags("desktop");
test("Drop file on HomeMenu should not trigger the share target dialog if not having share target items", async () => {
    const files = [new File([new Uint8Array(1)], "text.png", { type: "image/png" })];
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });
    const { moveTo } = await drag(".o-main-components-container", { files });
    await moveTo(".o_home_menu");
    await animationFrame();
    expect(".o-Dropzone").toHaveCount(0);
});

test("[Offline] unavailable apps are disabled", async () => {
    const setOffline = mockOffline();
    patchWithCleanup(OfflinePlugin.prototype, {
        isAvailableOffline(actionId) {
            return actionId === 123;
        },
    });
    await mountWithCleanup(HomeMenu, {
        props: getDefaultHomeMenuProps(),
    });

    expect(".o_app").toHaveCount(3);

    await setOffline(true);
    expect(".o_app.o_disabled_offline").toHaveCount(2);
    expect(".o_app:eq(2)").not.toHaveClass("o_disabled_offline");
});
