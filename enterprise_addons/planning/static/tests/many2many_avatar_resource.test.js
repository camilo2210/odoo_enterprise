import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, queryAll, queryAllTexts, queryFirst, waitFor } from "@odoo/hoot-dom";
import { animationFrame, mockDate, runAllTimers } from "@odoo/hoot-mock";

import { startServer } from "@mail/../tests/mail_test_helpers";

import {
    contains,
    defineActions,
    getService,
    mountView,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

import { definePlanningModels } from "./planning_mock_models";

describe.current.tags("desktop");

/* Main Goals of these tests:
- Tests the change made in planning to avatar card preview for resource:
- Roles appear as tags on the card
- Card should be displayed for material resources with at least 2 roles
- Adding a resource with assigned materials automatically adds its resource to the shift
*/
definePlanningModels();

const data = {};
beforeEach(async () => {
    /* 1. Create data
        4 type of resources will be tested in the widget:
        - material resource with only one role (Continuity testing computer)
            - clicking the icon should not open any popover
        - material resource with two roles (Integration testing computer)
            - clicking the icon should open a card popover with resource name and roles
        - human resource not linked to a user (Marie)
            - a card popover should open including the roles of the employee
        - human resource linked to a user (Pierre)
            - a card popover should open including the roles of the employee
    */
    const pyEnv = await startServer();
    [data.planningRoleTesterId, data.planningRoleItSpecialistId] = pyEnv["planning.role"].create([
        {
            name: "Tester",
            color: 1,
        },
        {
            name: "It Specialist",
            color: 2,
        },
    ]);

    data.partnerPierreId = pyEnv["res.partner"].create({
        name: "Pierre",
        email: "Pierre@odoo.test",
        phone: "+32487898933",
    });
    data.resUsersPierreId = pyEnv["res.users"].create({
        name: "Pierre",
        partner_id: data.partnerPierreId,
        im_status: "online",
    });
    [
        data.resourceMaterial1,
        data.resourceMaterial2,
        data.resourceMarieId,
        data.resourcePierreId,
        data.resourceBertrandId,
        data.resourceJoesphId,
        data.resourceLucieId,
    ] = pyEnv["resource.resource"].create([
        {
            name: "Continuity testing computer",
            resource_type: "material",
            role_ids: [data.planningRoleTesterId],
            assigned_employee_id: false,
        },
        {
            name: "Integration testing computer",
            resource_type: "material",
            role_ids: [data.planningRoleTesterId, data.planningRoleItSpecialistId],
            assigned_employee_id: false,
        },
        {
            name: "Marie",
            resource_type: "user",
            role_ids: [data.planningRoleTesterId],
        },
        {
            name: "Pierre",
            resource_type: "user",
            role_ids: [data.planningRoleItSpecialistId],
            user_id: data.resUsersPierreId,
        },
        { name: "Bertrand", resource_type: "user" },
        { name: "Joseph", resource_type: "user" },
        { name: "Lucie", resource_type: "user" },
    ]);

    [
        data.employeeMarieId,
        data.employeePierreId,
        data.employeeBertrandId,
        data.employeeJosephId,
        data.employeeLucieId,
    ] = pyEnv["hr.employee"].create([
        {
            name: "Marie",
            resource_id: data.resourceMarieId,
        },
        {
            name: "Pierre",
            resource_id: data.resourcePierreId,
            user_id: data.resUsersPierreId,
            user_partner_id: data.partnerPierreId,
        },
        { name: "Bertrand", resource_id: data.resourceBertrandId },
        { name: "Joseph", resource_id: data.resourceJoesphId },
        { name: "Lucie", resource_id: data.resourceLucieId },
    ]);

    [data.resourceMaterialDrillId, data.resourceMaterialSanderId] = pyEnv[
        "resource.resource"
    ].create([
        { name: "Drill", resource_type: "material", assigned_employee_id: data.employeeBertrandId },
        { name: "Sander", resource_type: "material", assigned_employee_id: data.employeeJosephId },
    ]);

    // Imitating the server behavior by creating an hr.employee.public record with the same data and same id
    [data.employeePublicMarieId, data.employeePublicPierreId] = pyEnv["hr.employee.public"].create([
        {
            name: "Marie",
        },
        {
            name: "Pierre",
            user_id: data.resUsersPierreId,
            user_partner_id: data.partnerPierreId,
        },
    ]);

    [
        data.planningSlotId1,
        data.planningSlotId2,
        data.planningSlotId3,
        data.planningSlotId4,
        data.planningSlotId5,
        data.unscheduleSlotId,
    ] = pyEnv["planning.slot"].create([
        {
            display_name: "Planning Slot tester 1",
            resource_ids: [data.resourceMaterial1],
            resource_roles: [data.planningRoleTesterId],
            user_ids: false,
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
        {
            display_name: "Planning slot integration tester",
            resource_ids: [data.resourceMaterial2],
            resource_roles: [data.planningRoleTesterId, data.planningRoleItSpecialistId],
            user_ids: false,
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
        {
            display_name: "Planning slot Marie",
            resource_ids: [data.resourceMarieId],
            resource_roles: [data.planningRoleTesterId],
            user_ids: false,
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
        {
            display_name: "Planning Slot Pierre",
            resource_ids: [data.resourcePierreId],
            resource_roles: [data.planningRoleItSpecialistId],
            user_ids: [data.resUsersPierreId],
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
        {
            display_name: "Planning Slot With 4 resources",
            resource_ids: [
                data.resourceMaterial1,
                data.resourceMaterial2,
                data.resourceMarieId,
                data.resourcePierreId,
            ],
            resource_roles: [data.planningRoleTesterId, data.planningRoleItSpecialistId],
            user_ids: [data.resUsersPierreId],
            start_datetime: "2023-11-09 00:00:00",
            end_datetime: "2023-11-09 22:00:00",
        },
        { name: "Test Slot" },
    ]);
});

defineActions([
    {
        id: 1,
        name: "PlanningSlot",
        res_model: "planning.slot",
        res_id: 5,
        views: [[false, "form"]],
    },
]);

test("many2many_avatar_resource widget in form view", async () => {
    await mountWithCleanup(WebClient);
    await getService("action").doAction(1);

    expect("img.o_m2m_avatar").toHaveCount(2);
    expect("[data-icon='build']").toHaveCount(2);

    // 1. Clicking on material resource's icon with only one role
    await click(".many2many_tags_avatar_field_container .o_tag i[data-icon='build']");
    await animationFrame();
    expect(".o_avatar_card").toHaveCount(0);

    // 2. Clicking on material resource's icon with two roles
    await click(queryAll(".many2many_tags_avatar_field_container .o_tag i[data-icon='build']")[1]);
    await waitFor(".o-mail-avatar-card-name:text(Integration testing computer)");
    expect(".o_avatar_card .o_avatar > img").toHaveCount(0, {
        message: "There should not be any avatar for material resource",
    });
    expect(".o_avatar_card_buttons button").toHaveCount(0);
    expect(".o_avatar_card .o_resource_roles_tags .o_tag").toHaveCount(2, {
        message: "Roles should be listed in the card",
    });

    // 3. Clicking on human resource's avatar with no user associated
    await click(".many2many_tags_avatar_field_container .o_tag img");
    await waitFor(".o-mail-avatar-card-name:text(Marie)");
    expect(".o_avatar_card").toHaveCount(1, {
        message: "Only one popover resource card should be opened at a time",
    });

    // 4. Clicking on human resource's avatar with one user associated
    await click(queryAll(".many2many_tags_avatar_field_container .o_tag img")[1]);
    await waitFor(".o-mail-avatar-card-name:text(Pierre)");
    expect(".o_avatar_card").toHaveCount(1, {
        message: "Only one popover resource card should be opened at a time",
    });
});

test("many2many_avatar_resource widget adds assigned materials in form view", async () => {
    await mountView({
        resModel: "planning.slot",
        type: "form",
        arch: `
            <form js_class="planning_form">
                <field name="name"/>
                <field name="resource_ids" widget="planning_many2many_avatar_resource"/>
            </form>
        `,
        resId: data.unscheduleSlotId,
    });

    const selectResource = async (name) => {
        await contains("div[name=resource_ids] input").edit(name);
        await runAllTimers();
    };
    const deleteResource = async (name) => {
        await click(`span.o_tag:contains(${name}) .o_delete`);
        await animationFrame();
    };

    await selectResource("Lucie");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual(["Lucie"]);
    await selectResource("Bertrand");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
    ]);
    await deleteResource("Bertrand");
    await deleteResource("Drill");
    await animationFrame();
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual(["Lucie"]);
    await selectResource("Bertrand");
    await selectResource("Sander");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
        "Sander",
    ]);
});

test("many2many_avatar_resource widget adds assigned materials in list view", async () => {
    await mountView({
        resModel: "planning.slot",
        type: "list",
        arch: `
            <list editable="bottom">
                <field name="name"/>
                <field name="resource_ids" widget="planning_many2many_avatar_resource"/>
            </list>
        `,
        domain: [["id", "=", data.unscheduleSlotId]],
    });

    const selectResource = async (name) => {
        await click("div[name=resource_ids]");
        await animationFrame();
        await contains(".o_input_dropdown input").edit(name);
        await runAllTimers();
    };
    const deleteResource = async (name) => {
        await click(`span.o_tag:contains(${name}) .o_delete`);
        await animationFrame();
    };

    await selectResource("Lucie");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual(["Lucie"]);
    await selectResource("Bertrand");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
    ]);
    await deleteResource("Bertrand");
    await deleteResource("Drill");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual(["Lucie"]);
    await selectResource("Bertrand");
    await selectResource("Sander");
    expect(queryAllTexts(".many2many_tags_avatar_field_container .o_tag")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
        "Sander",
    ]);
});

test("many2many_avatar_resource widget adds assigned materials in kanban view", async () => {
    await mountView({
        resModel: "planning.slot",
        type: "kanban",
        arch: `
            <kanban>
                <templates>
                    <t t-name="card">
                        <field name="name"/>
                        <field name="resource_ids" widget="planning_many2many_avatar_resource"/>
                    </t>
                </templates>
            </kanban>
        `,
        domain: [["id", "=", data.unscheduleSlotId]],
    });

    const selectResource = async (name) => {
        await contains("div.many2many_tags_avatar_field_container input").edit(name);
        await runAllTimers();
    };
    const deleteResource = async (name) => {
        await click(`span.o_tag:contains(${name}) .o_delete`);
        await animationFrame();
    };

    await click(".o_quick_assign");
    await animationFrame();
    await selectResource("Lucie");
    expect(queryAllTexts(".o_popover .o_field_many2many_tags_avatar .o_tag_badge_text")).toEqual([
        "Lucie",
    ]);
    await selectResource("Bertrand");
    expect(queryAllTexts(".o_popover .o_field_many2many_tags_avatar .o_tag_badge_text")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
    ]);
    await deleteResource("Bertrand");
    await deleteResource("Drill");
    expect(queryAllTexts(".o_popover .o_field_many2many_tags_avatar .o_tag_badge_text")).toEqual([
        "Lucie",
    ]);
    await selectResource("Bertrand");
    expect(queryAllTexts(".o_popover .o_field_many2many_tags_avatar .o_tag_badge_text")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
    ]);
    await selectResource("Continuity testing computer");
    expect(queryAllTexts(".o_popover .o_field_many2many_tags_avatar .o_tag_badge_text")).toEqual([
        "Lucie",
        "Bertrand",
        "Drill",
        "Continuity testing computer",
    ]);
});

test("many2many_avatar_resource widget in kanban view", async () => {
    await mountView({
        resModel: "planning.slot",
        type: "kanban",
        arch: `<kanban>
                <templates>
                    <t t-name="card">
                        <field name="display_name"/>
                        <field name="resource_ids" widget="many2many_avatar_resource"/>
                    </t>
                </templates>
            </kanban>
        `,
        domain: [["start_datetime", "!=", false]],
    });

    expect(".o_field_many2many_avatar_resource").toHaveCount(5);

    // build icon should be displayed for first two planning slots
    expect(".o_field_many2many_avatar_resource i[data-icon='build']").toHaveCount(3, {
        message:
            "material icon should be displayed for the first two gantt rows (material resources)",
    });

    // Third and fourth slots should display employee avatar
    expect(".o_field_many2many_avatar_resource img").toHaveCount(2);
    expect(
        queryFirst(
            ".o_kanban_record:nth-of-type(3) .o_field_many2many_avatar_resource img"
        ).getAttribute("data-src")
    ).toBe("/web/image/resource.resource/3/avatar_128", {
        message: "There should be the ID 3 in the URL as it is the one of resource 'Marie'",
    });
    expect(
        queryFirst(
            ".o_kanban_record:nth-of-type(4) .o_field_many2many_avatar_resource img"
        ).getAttribute("data-src")
    ).toBe("/web/image/resource.resource/4/avatar_128", {
        message: "There should be the ID 4 in the URL as it is the one of resource 'Pierre'",
    });

    // 1. Clicking on human resource's avatar with no user associated
    await click(".o_kanban_record:nth-of-type(3) .o_field_many2many_avatar_resource img");
    await waitFor(".o-mail-avatar-card-name:text(Marie)");

    // 2. Clicking on human resource's avatar with one user associated
    await click(".o_kanban_record:nth-of-type(4) .o_field_many2many_avatar_resource img");
    await waitFor(".o-mail-avatar-card-name:text(Pierre)");
});

test("Employee avatar in Gantt view", async () => {
    mockDate("2023-11-08 8:00:00", 0);
    onRpc("gantt_resource_work_interval", () => [
        {
            1: [
                ["2022-10-10 06:00:00", "2022-10-10 10:00:00"], //Monday    4h
                ["2022-10-11 06:00:00", "2022-10-11 10:00:00"], //Tuesday   5h
                ["2022-10-11 11:00:00", "2022-10-11 12:00:00"],
                ["2022-10-12 06:00:00", "2022-10-12 10:00:00"], //Wednesday 6h
                ["2022-10-12 11:00:00", "2022-10-12 13:00:00"],
                ["2022-10-13 06:00:00", "2022-10-13 10:00:00"], //Thursday  7h
                ["2022-10-13 11:00:00", "2022-10-13 14:00:00"],
                ["2022-10-14 06:00:00", "2022-10-14 10:00:00"], //Friday    8h
                ["2022-10-14 11:00:00", "2022-10-14 15:00:00"],
            ],
        },
    ]);
    onRpc("get_gantt_data", ({ kwargs, parent }) => {
        const result = parent();
        expect(kwargs.progress_bar_fields).toEqual(["resource_ids"]);
        result.progress_bars.resource_ids = {
            1: {
                value: 100,
                max_value: 100,
                is_material_resource: true,
                resource_color: 1,
                display_popover_material_resource: false,
                employee_id: false,
                work_intervals: [
                    ["2022-10-10 06:00:00", "2022-10-10 10:00:00"], //Monday    4h
                    ["2022-10-11 06:00:00", "2022-10-11 10:00:00"], //Tuesday   5h
                    ["2022-10-11 11:00:00", "2022-10-11 12:00:00"],
                    ["2022-10-12 06:00:00", "2022-10-12 10:00:00"], //Wednesday 6h
                    ["2022-10-12 11:00:00", "2022-10-12 13:00:00"],
                    ["2022-10-13 06:00:00", "2022-10-13 10:00:00"], //Thursday  7h
                    ["2022-10-13 11:00:00", "2022-10-13 14:00:00"],
                    ["2022-10-14 06:00:00", "2022-10-14 10:00:00"], //Friday    8h
                    ["2022-10-14 11:00:00", "2022-10-14 15:00:00"],
                ],
            },
            2: {
                value: 100,
                max_value: 100,
                is_material_resource: true,
                resource_color: 1,
                display_popover_material_resource: true, // Testing this full behavior would require a tour
                employee_id: false,
            },
            3: {
                value: 100,
                max_value: 100,
                is_material_resource: false,
                resource_color: false,
                display_popover_material_resource: false,
                employee_id: 1,
            },
            4: {
                value: 100,
                max_value: 100,
                is_material_resource: false,
                resource_color: false,
                display_popover_material_resource: false,
                employee_id: 2,
            },
        };
        return result;
    });
    await mountView({
        resModel: "planning.slot",
        type: "gantt",
        arch: `<gantt js_class="planning_gantt" date_start="start_datetime" date_stop="end_datetime" progress_bar="resource_ids"/>`,
        groupBy: ["resource_ids"],
    });
    expect(".o_gantt_row_title .o_avatar").toHaveCount(4);
    expect(".o_avatar .o_material_resource [data-icon='build']").toHaveCount(2, {
        message:
            "material icon should be displayed for the first two gantt rows (material resources)",
    });
    expect(".o_gantt_row_title .o_avatar img").toHaveCount(2, {
        message: "avatar should be displayed for the third and fourth gantt rows (human resources)",
    });
    expect(queryAll(".o_gantt_row_title .o_avatar img")[1].getAttribute("data-src")).toBe(
        "/web/image/resource.resource/4/avatar_128",
        {
            message:
                "avatar of the employee associated to the human resource should be displayed on fourth row",
        }
    );

    // 1. Clicking on material resource's icon with only one role
    await click(".o_avatar .o_material_resource [data-icon='build']");
    await animationFrame();
    expect(".o_avatar_card").toHaveCount(0);

    // 2. Clicking on material resource's icon with two roles
    await click(queryAll(".o_avatar .o_material_resource [data-icon='build']")[1]);
    await waitFor(".o-mail-avatar-card-name:text(Integration testing computer)")
    expect(".o_avatar_card .o_avatar > img").toHaveCount(0, {
        message: "There should not be any avatar for material resource",
    });
    expect(".o_avatar_card_buttons button").toHaveCount(0);
    expect(".o_avatar_card .o_resource_roles_tags .o_tag").toHaveCount(2, {
        message: "Roles should be listed in the card",
    });

    // 3. Clicking on human resource's avatar with no user associated
    await click(".o_gantt_row_title .o_avatar img");
    await waitFor(".o-mail-avatar-card-name:text(Marie)");
    expect(".o_avatar_card").toHaveCount(1, {
        message: "Only one popover resource card should be opened at a time",
    });

    // 4. Clicking on human resource's avatar with one user associated
    await click(queryAll(".o_gantt_row_title .o_avatar img")[1]);
    await waitFor(".o-mail-avatar-card-name:text(Pierre)");
    expect(".o_avatar_card").toHaveCount(1, {
        message: "Only one popover resource card should be opened at a time",
    });
});
