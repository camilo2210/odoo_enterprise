import { expect, test } from "@odoo/hoot";
import { defineMenus, mountWebClient, onRpc } from "@web/../tests/web_test_helpers";
import { animationFrame } from "@odoo/hoot-dom";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { IndexedDB } from "@web/core/utils/indexed_db";

test("use stored menus, and update on load_menus return", async () => {
    const def = Promise.withResolvers();
    onRpc("/web/webclient/load_menus", () => def.promise);
    defineMenus([
        {
            id: 1,
            appID: 1,
            actionID: 1,
            xmlid: "",
            name: "Partners",
            children: [],
            webIconData: "",
            webIcon: "bloop,bloop",
        },
        {
            id: 2,
            appID: 2,
            actionID: 2,
            xmlid: "",
            name: "CRM",
            children: [],
            webIconData: "",
            webIcon: "bloop,bloop",
        },
    ]);
    // Initial Stored Values
    // There is no menu "CRM" in the initial values
    const menuDB = new IndexedDB("webclient_menu");
    menuDB.write(
        "menu",
        JSON.stringify({ debug: false }),
        JSON.stringify({
            1: {
                id: 1,
                appID: 1,
                actionID: 1,
                xmlid: "",
                name: "Partners",
                children: [],
                webIconData: "",
                webIcon: "bloop,bloop",
            },
            root: { id: "root", name: "root", appID: "root", children: [1] },
        })
    );
    const webClient = await mountWebClient({ WebClient: WebClientEnterprise });
    webClient.env.bus.addEventListener("MENUS:APP-CHANGED", () => expect.step("Update Menus"));
    expect(".o_home_menu").toHaveCount(1);
    expect(".o_app").toHaveCount(1);
    expect.verifySteps([]);
    def.resolve();
    await animationFrame();
    expect(".o_app").toHaveCount(2);
    expect(JSON.parse(menuDB.mockIndexedDB.menu[JSON.stringify({ debug: false })])).toEqual({
        1: {
            actionID: 1,
            appID: 1,
            children: [],
            id: 1,
            name: "Partners",
            webIcon: "bloop,bloop",
            webIconData: "",
            xmlid: "",
        },
        2: {
            actionID: 2,
            appID: 2,
            children: [],
            id: 2,
            name: "CRM",
            webIcon: "bloop,bloop",
            webIconData: "",
            xmlid: "",
        },
        root: {
            appID: "root",
            children: [1, 2],
            id: "root",
            name: "root",
        },
    });
    expect.verifySteps(["Update Menus"]);
});
