import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { beforeEach, describe, expect, queryOne, test, queryAllTexts } from "@odoo/hoot";
import { waitFor } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    contains,
    defineActions,
    defineModels,
    fields,
    getService,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClientEnterprise } from "@web_enterprise/webclient/webclient";
import { editView, handleDefaultStudioRoutes, openStudio } from "../view_editor_tests_utils";

describe.current.tags("desktop");

defineMailModels();

class Partner extends models.Model {
    _name = "partner";

    name = fields.Char();
    partner_latitude = fields.Float();
    partner_longitude = fields.Float();
    contact_address_complete = fields.Char();
    sequence = fields.Integer();
    task_ids = fields.One2many({ relation: "task" });

    _records = [
        {
            id: 1,
            name: "Foo",
            partner_latitude: 10.0,
            partner_longitude: 10.5,
            contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
            sequence: 1,
        },
    ];
}

class Task extends models.Model {
    _name = "task";

    name = fields.Char();
    scheduled_date = fields.Char();
    sequence = fields.Integer();
    description = fields.Char();
    partner_id = fields.Many2one({ relation: "partner" });
    o2m_field = fields.One2many({ relation: "partner" });
    m2m_field = fields.Many2many({ relation: "partner" });
    binary_field = fields.Binary();

    _records = [
        {
            id: 1,
            name: "first record",
            description: "first description",
            partner_id: 1,
        },
    ];

    _views = {
        "map,1": `
            <map res_partner='partner_id' routing='ordered' hide_name='true' hide_address='true' studio_map_field_ids="[1,2]">
                <field name='name' string='Name'/>
                <field name='description' string='Description'/>
            </map>`,
        search: "<search/>",
    };
}

defineModels([Partner, Task]);

handleDefaultStudioRoutes();

beforeEach(() => {
    onRpc("res.company", "web_read", () => [
        {
            partner_id: {
                contact_address_complete: false,
                partner_latitude: 10.0,
                partner_longitude: 10.5,
            },
        },
    ]);
});

test("marker popup fields in editor sidebar", async () => {
    expect.assertions(12);

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0]).toEqual({
            type: "map_popup_fields",
            target: { field_ids: [1], operation_type: "remove" },
        });
        const arch = `
            <map res_partner='partner_id' routing='ordered' hide_name='true' hide_address='true' studio_map_field_ids="[2]">
                <field name='description' string='Description'/>
            </map>`;

        return editView(params, "map", arch);
    });

    await getService("action").doAction({
        name: "Task",
        res_model: "task",
        type: "ir.actions.act_window",
        view_mode: "map",
        views: [
            [1, "map"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    expect(".o_web_studio_sidebar .o_map_popup_fields").toHaveCount(1);
    expect(".o_web_studio_sidebar .o_map_popup_fields .badge").toHaveCount(2);
    expect("div.leaflet-marker-icon").toHaveCount(2);

    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > div:nth-child(1)").toHaveText("Name");
    expect(".o_map_card_grid > div:nth-child(2)").toHaveText("first record");
    expect(".o_map_card_grid > div:nth-child(3)").toHaveText("Description");
    expect(".o_map_card_grid > div:nth-child(4)").toHaveText("first description");

    await contains(".o_web_studio_sidebar .o_map_popup_fields .badge .o_delete").click();
    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_sidebar .o_map_popup_fields .badge").toHaveCount(1);

    await contains("div.leaflet-marker-icon").click();
    expect(".o_map_card_grid > *").toHaveCount(2);
    expect(".o_map_card_grid > div:nth-child(2)").toHaveText("first description");
});

test("map additional fields domain", async () => {
    expect.assertions(2);

    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    onRpc("ir.model.fields", "name_search", ({ kwargs }) => {
        expect.step("name_search");
        expect(kwargs.domain).toEqual([
            "&",
            "&",
            ["model", "=", "task"],
            ["ttype", "not in", ["many2many", "one2many", "binary"]],
            "!",
            ["id", "in", [1, 2]],
        ]);
    });

    await getService("action").doAction({
        name: "Task",
        res_model: "task",
        type: "ir.actions.act_window",
        view_mode: "map",
        views: [
            [1, "map"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    await contains(".o_field_many2many_tags input").click();
    expect.verifySteps(["name_search"]);
});

test("map routing options", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Task",
        res_model: "task",
        type: "ir.actions.act_window",
        view_mode: "map",
        views: [
            [1, "map"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    await contains("input.o_select_menu_toggler:eq(1)").click();
    expect(queryAllTexts(".o_select_menu_item")).toEqual(["Disabled", "Ordered", "Optimized"]);
});

test("many2many, one2many and binary fields cannot be selected in SortBy dropdown for map editor", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    await getService("action").doAction({
        name: "Task",
        res_model: "task",
        type: "ir.actions.act_window",
        view_mode: "map",
        views: [
            [1, "map"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    await contains("input.o_select_menu_toggler:eq(2)").click();
    // There are 3 hidden fields that are not defined above in the class (id, create_date, write_date)
    expect(".o_select_menu_item").toHaveCount(8);
});

test("map leaflet is rendered", async () => {
    defineActions([
        {
            xml_id: "action_2",
            name: "task Action 2",
            res_model: "task",
            type: "ir.actions.act_window",
            views: [[1, "map"]],
        },
    ]);
    await mountWithCleanup(WebClientEnterprise);
    await waitFor(".o_home_menu");

    getService("action").doAction("action_2");
    await waitFor(".o-map-renderer--container.leaflet-container");
    let mapContainer = queryOne(".o-map-renderer--container.leaflet-container");
    let mapRect = mapContainer.getBoundingClientRect();
    expect(mapRect.width).toBeGreaterThan(0);
    expect(mapRect.height).toBeGreaterThan(0);

    await openStudio();
    await waitFor(".o_web_studio_view_renderer .o-map-renderer--container.leaflet-container");
    mapContainer = queryOne(".o-map-renderer--container.leaflet-container");
    mapRect = mapContainer.getBoundingClientRect();
    expect(mapRect.width).toBeGreaterThan(0);
    expect(mapRect.height).toBeGreaterThan(0);
});

test("can create toggle in editor sidebar", async () => {
    await mountWithCleanup(WebClientEnterprise);
    await animationFrame();

    onRpc("/web_studio/edit_view", async (request) => {
        const { params } = await request.json();
        expect.step("edit_view");
        expect(params.operations[0].new_attrs).toEqual({ create: false });
        const arch = `
            <map res_partner='partner_id' routing='ordered' hide_name='true' hide_address='true' studio_map_field_ids="[1,2]" create='false'>
                <field name='name' string='Name'/>
                <field name='description' string='Description'/>
            </map>`;
        return editView(params, "map", arch);
    });

    await getService("action").doAction({
        name: "Task",
        res_model: "task",
        type: "ir.actions.act_window",
        view_mode: "map",
        views: [
            [1, "map"],
            [false, "search"],
        ],
        group_ids: [],
    });

    await contains(".o_web_studio_navbar_item").click();
    expect(".o_web_studio_sidebar input#create").toBeChecked();

    await contains(".o_web_studio_sidebar input#create").click();
    expect.verifySteps(["edit_view"]);
    expect(".o_web_studio_sidebar input#create").not.toBeChecked();
});
