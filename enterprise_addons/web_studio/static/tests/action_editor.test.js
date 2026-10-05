import { describe, expect, test, waitFor } from "@odoo/hoot";
import { edit, press } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    mountWithCleanup,
    onRpc,
    getService,
    models,
    fields,
    defineModels,
    defineActions,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { defineStudioEnvironment } from "./studio_tests_context";

describe.current.tags("desktop");

defineStudioEnvironment();

test("add a gantt view", async () => {
    expect.assertions(5);

    onRpc("/web_studio/add_view_type", async (request) => {
        const { params } = await request.json();
        expect(params.view_type).toBe("gantt");
    });

    onRpc("fields_get", ({ model }) => {
        expect(model).toBe("partner");
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_menu_sections button:contains(Views)").click();
    await contains(".o_web_studio_thumbnail_item.o_web_studio_thumbnail_gantt").click();

    expect(".o_web_studio_new_view_dialog").toHaveCount(1);
    expect(".o_web_studio_new_view_dialog select[name='date_start']").toHaveValue("create_date");
    expect(".o_web_studio_new_view_dialog select[name='date_stop']").toHaveValue("create_date");
});

test("create unavailable view", async () => {
    expect.assertions(1);
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_menu_sections button:contains(Views)").click();
    await contains(".o_web_studio_thumbnail_item.o_web_studio_thumbnail_activity").click();

    expect(".o_notification_content").toHaveText("Activity view unavailable on this model");
});

test("disable the view from studio", async () => {
    let listIsDisabled = false;

    onRpc("/web_studio/edit_action", async () => {
        listIsDisabled = true;
        return true;
    });

    onRpc("/web/action/load", async () => {
        if (listIsDisabled) {
            return {
                id: 1,
                name: "partner Action (kanban first)",
                res_model: "partner",
                type: "ir.actions.act_window",
                xml_id: "partner_action_1",
                view_mode: "kanban",
                views: [
                    [1, "kanban"],
                    [false, "grid"],
                    [false, "search"],
                    [false, "form"],
                ],
                group_ids: [],
            };
        }
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_menu_sections button:contains(Views)").click();
    await contains(".o_web_studio_thumbnail_list .o_web_studio_more").click();
    await contains(".o-dropdown-item:contains('Disable View')").click();

    expect(".o_web_studio_thumbnail_list.disabled").toHaveCount(1);

    await contains(".o_web_studio_thumbnail_kanban .o_web_studio_more").click();
    await contains(".o-dropdown-item:contains('Disable View')").click();

    expect(".o_technical_modal .modal-body").toHaveText(
        "You cannot deactivate this view as it is the last one active."
    );
});

test("add groups on action", async () => {
    onRpc("/web_studio/edit_action", async (request) => {
        const { params } = await request.json();
        expect(params.args.group_ids[0]).toEqual([4, 11]);
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_menu_sections button:contains(Views)").click();

    await contains("input#group_ids").click();
    await contains(".o-autocomplete--dropdown-item .dropdown-item:nth-child(1)").click();
});

test("concurrency: keep user's input when editing action", async () => {
    const def = Promise.withResolvers();
    let actionName = "Partner View";
    onRpc("/web_studio/edit_action", async (request) => {
        const { params } = await request.json();
        expect(params.args).toEqual({ name: "testInput" });
        expect.step("edit_action");
        actionName = params.args.name;
        await def.promise;
    });
    onRpc("/web/action/load", async () => {
        expect.step("load_action");
        return {
            id: 1,
            name: actionName,
            res_model: "partner",
            type: "ir.actions.act_window",
            xml_id: "partner_action_1",
            view_mode: "kanban",
            views: [
                [1, "kanban"],
                [2, "list"],
                [false, "grid"],
                [false, "search"],
                [false, "form"],
            ],
            group_ids: [],
        };
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await contains(".o_menu_sections button:contains(Views)").click();
    expect.verifySteps(["load_action"]);

    await contains(".o_web_studio_sidebar_content input#name").click();
    await edit("testInput");
    await animationFrame();
    await contains(".o_web_studio_sidebar_content textarea#help").click();
    await edit("<p>test help</p>");

    def.resolve();
    await def.promise;
    await animationFrame();

    expect.verifySteps(["edit_action", "load_action"]);
    expect(".o_web_studio_sidebar_content input#name").toHaveValue("testInput");
    expect(".o_web_studio_sidebar_content textarea#help").toHaveValue("<p>test help</p>");
});

test("active_id and active_ids present in context at reload", async () => {
    onRpc("/web_studio/edit_action", async () => {
        expect.step("edit_action");
    });
    onRpc("/web/action/load", async (request) => {
        const { params } = await request.json();
        expect.step(`load_action: ${JSON.stringify(params)}`);
    });

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await contains(".o_app[data-menu-xmlid=app_1]").click();
    await animationFrame();
    expect.verifySteps([
        `load_action: {"action_id":1,"context":{"lang":"en","tz":"taht","uid":7,"allowed_company_ids":[1]}}`,
    ]);

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_menu_sections button:contains(Views)").click();

    await contains(".o_web_studio_sidebar_content input#name").click();
    await edit("testInput");
    await animationFrame();
    await press("Tab");
    await animationFrame();

    expect.verifySteps([
        "edit_action",
        `load_action: {"action_id":1,"context":{"lang":"en","tz":"taht","uid":7,"allowed_company_ids":[1]}}`,
    ]);
});

test("add map view", async () => {
    onRpc("/web_studio/add_view_type", async (request) => {
        const { params } = await request.json();
        expect.step("/web_studio/add_view_type");
        expect(params.view_type).toBe("map");
    });
    onRpc("/web_studio/create_default_view", async (request) => {
        const { params } = await request.json();
        expect.step("/web_studio/create_default_view");
        expect(params.view_type).toBe("map");
        Dummy._views = {
            map: `<map><field name="display_name" /></map>`,
        };
    });
    onRpc("/web_studio/edit_action", async function (request) {
        const { params } = await request.json();
        expect.step("/web_studio/edit_action");
        expect(params).toEqual({
            action_id: 555,
            action_type: "ir.actions.act_window",
            args: {
                view_mode: "form,map",
            },
        });

        const action = this.actions.find((a) => a.id === params.action_id);
        action.view_mode = params.args.view_mode;
        action.views.push([false, "map"]);
    });

    class Dummy extends models.Model {
        _name = "dummy";
        partner_id = fields.Many2one({ relation: "res.partner" });
    }
    defineModels([Dummy]);
    defineActions([
        {
            id: 555,
            type: "ir.actions.act_window",
            views: [[false, "form"]],
            view_mode: "form",
            res_model: "dummy",
            group_ids: [],
        },
    ]);

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();
    await getService("action").doAction(555);
    await waitFor(".o_form_view");
    await animationFrame();

    await getService("studio").open();
    await contains(".o_studio .o_web_studio_menu .o_menu_sections button:contains(Views)").click();
    await contains(".o_web_studio_views .o_web_studio_thumbnail_map").click();
    expect.verifySteps(["/web_studio/add_view_type"]);
    await waitFor(".modal .modal-title:contains(Generate map View)");
    await contains(".modal-footer button:contains(Activate View)").click();
    expect.verifySteps(["/web_studio/create_default_view", "/web_studio/edit_action"]);

    await waitFor(".o_web_studio_editor_manager .o_map_view");
});
