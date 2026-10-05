import { beforeEach, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import {
    contains,
    getService,
    mountView,
    mountWebClient,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { session } from "@web/session";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";

import {
    definePlanningFieldServiceModels,
    planningFieldServiceModels,
} from "./planning_field_service_mock_models";
import { queryOne } from "@odoo/hoot-dom";
import { rgbToHex } from "@web/core/utils/colors";

definePlanningFieldServiceModels();

beforeEach(() => {
    mockDate("2026-01-04 12:00:00", 0);

    planningFieldServiceModels.PlanningSlot._views.map = `
        <map res_partner="partner_id" routing="ordered" js_class="planning_field_service_map">
            <field name="resource_ids" invisible="1"/>
            <field name="start_datetime" invisible="1"/>
            <field name="end_datetime" invisible="1"/>
        </map>`;

    patchWithCleanup(session, { map_box_token: "token" });

    patchWithCleanup(Geolocation.prototype, {
        async fetchRoute() {
            return {
                legs: [
                    {
                        steps: [
                            {
                                geometry: {
                                    coordinates: [
                                        [4.55, 50.2],
                                        [4.56, 50.3],
                                    ],
                                },
                            },
                        ],
                    },
                ],
                duration: 3000,
                distance: 10000,
            };
        },
    });
});

test("Routing popup does not contain the resource avatar if view is not grouped by resource", async () => {
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            resource_ids: [1],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
    ];

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["partner_id"],
    });

    expect("div.o-map-renderer--routing-popup").toHaveCount(1, {
        message: "There should be one route",
    });
    expect("div.o-map-renderer--routing-popup .o_planning_resource_avatar").toHaveCount(0, {
        message: "The popup should not contain the resource avatar",
    });
});

test("Routing popup does not display an avatar for records without resources", async () => {
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            resource_ids: [],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
    ];

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });

    expect("div.o-map-renderer--routing-popup .o_planning_resource_avatar").toHaveCount(0, {
        message: "No avatar should appear when groupId is 'None'",
    });
});

test("Routing popup contains the resource avatar if view is grouped by resources", async () => {
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            resource_ids: [1],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
    ];

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });

    expect(".leaflet-overlay-pane path").toHaveCount(1, {
        message: "There should be one route",
    });
    expect("div.o-map-renderer--routing-popup").toHaveCount(1, {
        message: "There should be one route popup",
    });
    expect("div.o-map-renderer--routing-popup .o_planning_resource_avatar").toHaveCount(1, {
        message: "The popup should contain the resource avatar",
    });
});

test.tags("desktop");
test("Routing popup shows a wrench icon instead of an avatar for material resource", async () => {
    planningFieldServiceModels.ResourceResource._records = [
        { id: 1, name: "Human", resource_type: "user" },
        { id: 2, name: "Material", resource_type: "material" },
    ];
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            resource_ids: [1],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
        {
            id: 2,
            name: "Intervention 2",
            resource_ids: [2],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
    ];

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });

    expect(
        "div.o-map-renderer--routing-popup .o_planning_resource_avatar i[data-icon='build']"
    ).toHaveCount(1, {
        message: "The material resource should display a wrench icon",
    });

    const avatar = queryOne(
        "div.o-map-renderer--routing-popup .o_planning_resource_avatar:has(i[data-icon='build'])"
    );
    expect(avatar).not.toBe(null, { message: "The material resource avatar should exist" });
    expect(avatar.style.backgroundColor).not.toBe("", {
        message: "The material resource avatar should have a background color",
    });

    const pinPath = queryOne(
        "div.o-map-renderer--pin-list-group-header:contains('Material') .o-map-renderer--pin-list-group-svg svg path:first"
    );
    const pinColor = pinPath.getAttribute("fill");
    expect(rgbToHex(avatar.style.backgroundColor).toUpperCase()).toBe(pinColor, {
        message: "The avatar background color should match the group's pin color",
    });
});

test.tags("desktop");
test("Map view folds material resources by default when grouped by resource", async () => {
    planningFieldServiceModels.ResourceResource._records = [
        { id: 1, name: "Human Resource", resource_type: "user" },
        { id: 2, name: "Material Resource", resource_type: "material" },
    ];
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            resource_ids: [1, 2],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
    ];

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });

    expect(
        "div.o-map-renderer--pin-list-group-header:contains('Material Resource') i[data-icon='arrow_right']"
    ).toHaveCount(1, {
        message: "The material resource group should be closed (has arrow_right)",
    });

    expect(
        "div.o-map-renderer--pin-list-group-header:contains('Human Resource') i[data-icon='arrow_drop_down']"
    ).toHaveCount(1, {
        message: "The human resource group should be open (has arrow_drop_down)",
    });
});

test.tags("desktop");
test("Map view keeps the groups folded by the user when switching away and back", async () => {
    planningFieldServiceModels.ResourceResource._records = [
        { id: 1, name: "Human Resource", resource_type: "user" },
        { id: 2, name: "Material Resource", resource_type: "material" },
    ];
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            resource_ids: [1, 2],
            partner_id: 520,
            start_datetime: "2026-01-04 12:00:00",
            end_datetime: "2026-01-04 14:00:00",
        },
    ];
    planningFieldServiceModels.PlanningSlot._views = {
        map: `
            <map default_group_by="resource_ids" res_partner="partner_id" js_class="planning_field_service_map">
                <field name="resource_ids" invisible="1"/>
                <field name="start_datetime" invisible="1"/>
                <field name="end_datetime" invisible="1"/>
            </map>`,
        list: `<list><field name="name"/></list>`,
        search: `<search/>`,
    };

    await mountWebClient();
    await getService("action").doAction({
        res_model: "planning.slot",
        type: "ir.actions.act_window",
        views: [
            [false, "map"],
            [false, "list"],
        ],
    });

    await contains(
        "div.o-map-renderer--pin-list-group-header:contains('Material Resource')"
    ).click();
    await contains("div.o-map-renderer--pin-list-group-header:contains('Human Resource')").click();

    await getService("action").switchView("list");
    expect(".o_list_view").toHaveCount(1);
    await getService("action").switchView("map");

    expect(
        "div.o-map-renderer--pin-list-group-header:contains('Material Resource') i[data-icon='arrow_drop_down']"
    ).toHaveCount(1, {
        message: "The material resource group unfolded by the user should stay unfolded",
    });
    expect(
        "div.o-map-renderer--pin-list-group-header:contains('Human Resource') i[data-icon='arrow_right']"
    ).toHaveCount(1, {
        message: "The human resource group folded by the user should stay folded",
    });
});
