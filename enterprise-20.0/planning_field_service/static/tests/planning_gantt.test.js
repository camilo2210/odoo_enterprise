import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, click, hover, queryAllTexts } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { dragPill } from "@web_gantt/../tests/web_gantt_test_helpers";
import { findComponent, mountView, onRpc, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { session } from "@web/session";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";
import { GanttController } from "@web_gantt/gantt_controller";
import { GanttRenderer } from "@web_gantt/gantt_renderer";

import { PlanningGanttModel } from "@planning/views/planning_gantt/planning_gantt_model";
import { PlanningFieldServiceRouting } from "@planning_field_service/views/planning_hooks";

import {
    definePlanningFieldServiceModels,
    planningFieldServiceModels,
} from "./planning_field_service_mock_models";

planningFieldServiceModels.ResPartner._records = [
    ...planningFieldServiceModels.ResPartner._records,
    {
        id: 1000,
        name: "Customer 1",
        contact_address_complete: "Rue du Blé 17, 6000 City, Belgium",
        partner_latitude: 50.0,
        partner_longitude: 10.5,
    },
    {
        id: 1001,
        name: "Customer 2",
        contact_address_complete: "Rue de l'Étan 21, 1000 Grenouille, Belgium",
        partner_latitude: 40.0,
        partner_longitude: 10.5,
    },
    {
        id: 1002,
        name: "Customer 3",
        contact_address_complete: "Avenue du Compte 190, 1234 Roi, Belgium",
        partner_latitude: 50.3,
        partner_longitude: 10.1,
    },
];
planningFieldServiceModels.PlanningSlot._records = [
    {
        id: 1,
        name: "Intervention 1",
        partner_id: 1000,
        resource_ids: [],
        start_datetime: "2026-04-20 08:00:00",
        end_datetime: "2026-04-20 15:00:00",
        can_edit: true,
    },
    {
        id: 2,
        name: "Intervention 2",
        partner_id: 1000,
        resource_ids: [],
        start_datetime: "2026-04-22 08:00:00",
        end_datetime: "2026-04-22 12:00:00",
        can_edit: true,
    },
    {
        id: 3,
        name: "Intervention 3",
        partner_id: 1001,
        resource_ids: [],
        start_datetime: "2026-04-22 13:00:00",
        end_datetime: "2026-04-22 16:00:00",
        can_edit: true,
    },
    {
        id: 4,
        name: "Intervention 4",
        partner_id: 1000,
        resource_ids: [2],
        start_datetime: "2026-04-22 08:00:00",
        end_datetime: "2026-04-22 11:00:00",
        can_edit: true,
    },
    {
        id: 5,
        name: "Intervention 5",
        partner_id: 1001,
        resource_ids: [1, 2],
        start_datetime: "2026-04-22 13:00:00",
        end_datetime: "2026-04-22 15:30:00",
        can_edit: true,
    },
    {
        id: 6,
        name: "Intervention 6",
        partner_id: 1002,
        resource_ids: [2],
        start_datetime: "2026-04-22 17:30:00",
        end_datetime: "2026-04-22 21:00:00",
        can_edit: true,
    },
];

definePlanningFieldServiceModels();

describe.current.tags("desktop");

beforeEach(() => {
    mockDate("2026-04-22 14:00:00");

    patchWithCleanup(session, { map_box_token: "token" });

    patchWithCleanup(PlanningFieldServiceRouting.prototype, {
        async computeTravelTimes() {
            expect.step("compute_travel_times");
            return super.computeTravelTimes(...arguments);
        },
    });
    patchWithCleanup(Geolocation.prototype, {
        async fetchRoute(coords, routing) {
            const legs = [];
            for (let i = 1; i < coords.length; i++) {
                const coordinates = [];
                coordinates[0] = [10, 10.5];
                coordinates[1] = [10, 10.6];
                const geometry = { coordinates };
                const steps = [];
                steps[0] = { geometry };
                legs.push({ steps: steps, duration: 1800, distance: 20000 });
            }
            if (legs.length == 0) {
                return null;
            }
            return { legs, duration: 3000, distance: 10000 };
        },
    });
    onRpc(({ method, parent }) => {
        if (method === "get_gantt_data") {
            const result = parent();
            result.resource_work_locations = {
                1: {
                    partner_latitude: 50.0,
                    partner_longitude: 10.0,
                },
                2: {
                    partner_latitude: 50.0,
                    partner_longitude: 10.0,
                },
            };
            return result;
        } else if (method === "update_slot_travel_times") {
            expect.step("update_slot_travel_times");
            return true;
        }
    });
});

test("Travel times are not computed if the user is not manager", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "planning.group_planning_manager") {
            return false;
        }
    });

    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps([], { message: "Travel times should not be computed" });
});

test("Travel times are not computed if the view scale is not 'day'", async () => {
    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "week" },
    });

    expect.verifySteps([], { message: "Travel times should not be computed" });
});

test("Travel times are not computed if MapBox is not enabled", async () => {
    patchWithCleanup(session, { map_box_token: "" });

    patchWithCleanup(PlanningGanttModel.prototype, {
        shouldComputeTravelTimesOnLoad: false,
        shouldUpdateTravelTimes: true,
    });

    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps([], { message: "Travel times should not be computed" });

    expect("button.o_gantt_button_update_travel_times").toHaveCount(0, {
        message: "The recompute button should not be displayed",
    });
});

test("Travel times are not computed if the view is not grouped by resources", async () => {
    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        context: { default_scale: "day" },
    });

    expect.verifySteps([], { message: "Travel times should not be computed" });
});

test("Travel times are not computed if there are already some in the view", async () => {
    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Intervention 1",
            partner_id: 1000,
            resource_ids: [1],
            start_datetime: "2026-04-22 08:00:00",
            end_datetime: "2026-04-22 15:00:00",
            travel_time_in: 0.5,
            travel_times_up_to_date: true,
        },
    ];

    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps([], { message: "Travel times should not be computed" });
});

test("Travel times are correctly computed if there is none in the view yet", async () => {
    const view = await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps(["compute_travel_times", "update_slot_travel_times"], {
        message: "Travel times should be computed",
    });
    expect(".o_notification").toHaveCount(0, {
        message: "At load, the notification should not appear",
    });
    expect("div.o_gantt_pill_buffer_content").toHaveCount(4);

    const model = findComponent(view, (c) => c instanceof GanttController).model;
    const openShifts = model.data.records.filter((r) => !r.resource_ids.length);
    expect(openShifts.some((r) => r.travel_time_in || r.travel_time_out)).toBe(false, {
        message: "There should not be any buffer computed for open shifts",
    });
});

test("Button to update buffer is displayed if view is not up-to-data, clicking updates them and button disappears", async () => {
    patchWithCleanup(PlanningGanttModel.prototype, {
        shouldComputeTravelTimesOnLoad: false,
    });

    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps([], {
        message: "Travel times should not be computed",
    });
    expect("button.o_gantt_button_update_travel_times").toHaveCount(1, {
        message: "The button to recompute travel times should be visible",
    });
    await click("button.o_gantt_button_update_travel_times");
    await animationFrame();

    expect.verifySteps(["compute_travel_times", "update_slot_travel_times"], {
        message: "Travel times should be computed",
    });
    expect("button.o_gantt_button_update_travel_times").toHaveCount(0, {
        message: "The button to recompute travel times should not be visible",
    });
    expect(".o_notification .o_notification_content").toHaveText(/Travel times updated/, {
        message: "The user should be notified that buffers were computed",
    });
});

test("Buffer end is displayed only if resource has no other shift later", async () => {
    const view = await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps(["compute_travel_times", "update_slot_travel_times"], {
        message: "Travel times should be computed",
    });

    const renderer = findComponent(view, (c) => c instanceof GanttRenderer);
    const pillWithBufferEnd = renderer.rowPills['[{"resource_ids":[1,"Mitchell Admin"]}]'].find(
        (p) => p.record.id === 5
    );
    expect(pillWithBufferEnd.buffer.column[1]).toBe(pillWithBufferEnd.grid.column[1] + 2, {
        message: "The buffer end should be displayed since the resource has no other slot",
    });
    const pillWithoutBufferEnd = renderer.rowPills['[{"resource_ids":[2,"Technician"]}]'].find(
        (p) => p.record.id === 5
    );
    expect(pillWithoutBufferEnd.buffer.column[1]).toBe(pillWithoutBufferEnd.grid.column[1], {
        message: "The buffer end should not be displayed since the resource has another slot",
    });
});

test("Drag and dropping a shift updates buffers visually", async () => {
    const view = await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps(["compute_travel_times", "update_slot_travel_times"], {
        message: "Travel times should be computed",
    });

    const { drop } = await dragPill("Intervention 6");
    await drop({
        row: "Technician",
        columnHeader: "5",
        groupHeader: "Wednesday, April 22, 2026",
    });
    await animationFrame();

    // In this test, we do not write on the records, so in practice it should not be recomputed
    expect.verifySteps(["compute_travel_times", "update_slot_travel_times"], {
        message: "Travel times should be computed",
    });

    const renderer = findComponent(view, (c) => c instanceof GanttRenderer);
    const pill = renderer.rowPills['[{"resource_ids":[2,"Technician"]}]'].find(
        (p) => p.record.id === 6
    );
    expect(pill.buffer.column[1]).toBe(pill.grid.column[1], {
        message: "The buffer end should not be displayed",
    });
    expect(pill.record.travel_time_out).not.toBe(0.0, {
        message: "The buffer should only be removed visually and should remain on the record",
    });
});

test("Hovering the buffer shows the travel time information", async () => {
    await mountView({
        type: "gantt",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
        context: { default_scale: "day" },
    });

    expect.verifySteps(["compute_travel_times", "update_slot_travel_times"], {
        message: "Travel times should be computed",
    });

    await hover("div.o_gantt_pill_buffer_content");
    await animationFrame();

    expect(queryAllTexts(".o_gantt_buffer_popover > div")).toEqual([
        "Travel time",
        "Depart at\n2:30 PM",
        "Duration\n0h 30m",
        "Distance\n20 km",
    ]);
});
