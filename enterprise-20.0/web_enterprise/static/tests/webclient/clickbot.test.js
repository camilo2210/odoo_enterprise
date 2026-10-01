import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import {
    defineActions,
    defineMenus,
    defineModels,
    fields,
    models,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { WebClient } from "@web/webclient/webclient";
import { ClickbotLauncher, SUCCESS_SIGNAL } from "@web/webclient/clickbot/clickbot";

class Foo extends models.Model {
    foo = fields.Char();
    bar = fields.Boolean();
    date = fields.Date();

    _records = [
        { id: 1, bar: true, foo: "yop", date: "2017-01-25" },
        { id: 2, bar: true, foo: "blip" },
        { id: 3, bar: true, foo: "gnap" },
        { id: 4, bar: false, foo: "blip" },
    ];

    _views = {
        search: /* xml */ `
            <search>
                <filter string="Not Bar" name="not bar" domain="[['bar','=',False]]"/>
                <filter string="Date" name="date" date="date"/>
            </search>
        `,
        list: /* xml */ `
            <list>
                <field name="foo" />
            </list>
        `,
        kanban: /* xml */ `
            <kanban class="o_kanban_test">
                <templates><t t-name="card">
                    <field name="foo"/>
                </t></templates>
            </kanban>
        `,
        form: /* xml */ `
            <form>
                <field name="foo" />
            </form>
        `,
    };
}

describe.current.tags("desktop");

defineModels([Foo]);

beforeEach(() => {
    defineActions([
        {
            id: 1001,
            name: "App1",
            res_model: "foo",
            views: [
                [false, "list"],
                [false, "kanban"],
                [false, "form"],
            ],
            xml_id: "app1",
        },
        {
            id: 1002,
            name: "App2 Menu 1",
            res_model: "foo",
            views: [
                [false, "kanban"],
                [false, "form"],
            ],
            xml_id: "app2_menu1",
        },
        {
            id: 1022,
            name: "App2 Menu 2",
            res_model: "foo",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            xml_id: "app2_menu2",
        },
    ]);
    defineMenus([
        { id: 1, name: "App1", appID: 1, actionID: 1001, xmlid: "app1" },
        {
            id: 2,
            children: [
                {
                    id: 3,
                    name: "menu 1",
                    appID: 2,
                    actionID: 1002,
                    xmlid: "app2_menu1",
                },
                {
                    id: 4,
                    name: "menu 2",
                    appID: 2,
                    actionID: 1022,
                    xmlid: "app2_menu2",
                },
            ],
            name: "App2",
            appID: 2,
            actionID: 1002,
            xmlid: "app2",
        },
    ]);
});

test("clickbot clickeverywhere test", async () => {
    onRpc("has_group", () => true);
    mockDate("2017-10-08T15:35:11.000");
    const { promise, resolve } = Promise.withResolvers();
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
    const webClient = await mountWithCleanup(WebClient);
    patchWithCleanup(odoo, {
        __WOWL_DEBUG__: { root: webClient },
    });
    patchWithCleanup(performance, {
        now: () => 43554.39999999106,
    });
    new ClickbotLauncher(webClient.env, { logger: true }).start();
    await promise;
    expect.verifySteps([
        "Starting ClickEverywhere test",
        "Testing app: App1 (app1)",
        "Testing menu App1 (app1)",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Clicking on: open form view from list",
        "Clicking on: go back to list view (from record view)",
        "Testing 2 filters",
        'Clicking on: filter "Not Bar"',
        'Clicking on: filter "Date"',
        'Clicking on: filter "Date (Today)"',
        "Testing view switch: kanban",
        "Clicking on: kanban view switcher",
        "Clicking on: kanban view's new button",
        "Clicking on: go back to kanban view (from new record form view)",
        "Testing 2 filters",
        'Clicking on: filter "Not Bar"',
        'Clicking on: filter "Date (Today)"',
        "Testing app: App2 (app2)",
        "Testing menu menu 1 (app2_menu1)",
        "Clicking on: kanban view's new button",
        "Clicking on: go back to kanban view (from new record form view)",
        "Clicking on: open form view from kanban",
        "Clicking on: go back to kanban view (from record view)",
        "Testing 2 filters",
        'Clicking on: filter "Not Bar"',
        'Clicking on: filter "Date"',
        'Clicking on: filter "Date (Today)"',
        "Testing menu menu 2 (app2_menu2)",
        "Clicking on: list view's new button",
        "Clicking on: go back to list view (from new record form view)",
        "Clicking on: open form view from list",
        "Clicking on: go back to list view (from record view)",
        "Testing 2 filters",
        'Clicking on: filter "Not Bar"',
        'Clicking on: filter "Date"',
        'Clicking on: filter "Date (Today)"',
        "Test took 0 seconds",
        "Tested 2 apps",
        "Tested 3 menus",
        "Tested 4 views",
        "Tested 3 form views",
        "Tested 4 new record views",
        "Tested 0 modals",
        "Tested 8 filters",
        SUCCESS_SIGNAL,
    ]);
});
