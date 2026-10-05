import { beforeEach, describe, expect, test } from "@odoo/hoot";
import {
    animationFrame,
    click,
    drag,
    edit,
    hover,
    queryAllTexts,
    queryFirst,
    queryOne,
    waitFor,
} from "@odoo/hoot-dom";
import { mockDate, runAllTimers } from "@odoo/hoot-mock";
import { parseDateTime, serializeDateTime } from "@web/core/l10n/dates";
import {
    defineActions,
    findComponent,
    getService,
    getTestApp,
    mountWebClient,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { clickCell, dragPill } from "@web_gantt/../tests/web_gantt_test_helpers";
import { GanttController } from "@web_gantt/gantt_controller";
import { MapController } from "@web_map/map_view/map_controller";

import {
    definePlanningFieldServiceModels,
    planningFieldServiceModels,
} from "./planning_field_service_mock_models";

definePlanningFieldServiceModels();

describe.current.tags("desktop");

defineActions([
    {
        id: 1,
        name: "Timeline",
        res_model: "planning.slot",
        type: "ir.actions.act_window",
        view_mode: "map,form",
        views: [
            [false, "map"],
            [false, "form"],
        ],
        context: { search_default_start_datetime: "today" },
    },
]);

async function mountMapTimeline() {
    const webClient = await mountWebClient();
    await getService("action").doAction(1);
    await waitFor(".o_gantt_view");
    return webClient;
}

/**
 * The embedded gantt sub-view is rendered through a <Portal/>, which mounts
 * its content as its own separate app root instead of a descendant of the
 * webClient's — findComponent() alone can't reach it, so every root has to
 * be searched.
 */
async function findComponentInAnyRoot(predicate) {
    for (const root of getTestApp().roots) {
        const component = await root.promise;
        const found = findComponent(component, predicate);
        if (found) {
            return found;
        }
    }
    return null;
}

/**
 * Odoo's "smart date" filter values (e.g. "today", "today +2d") are only
 * resolved to real dates server-side — the mock server's domain matcher
 * doesn't understand it and would filter out every record (see
 * Domain.prototype.contains's own doc comment). Resolve them to real dates
 * before the real mock model handlers evaluate the domain.
 */
function resolveSmartDateDomain(domain) {
    return domain.map((item) =>
        Array.isArray(item) && typeof item[2] === "string" && /^today\b/.test(item[2])
            ? [item[0], item[1], serializeDateTime(parseDateTime(item[2]))]
            : item
    );
}

beforeEach(() => {
    mockDate("2026-01-04 12:00:00", 0);

    onRpc(async ({ kwargs, parent }) => {
        if (Array.isArray(kwargs?.domain)) {
            kwargs.domain = resolveSmartDateDomain(kwargs.domain);
        }
        return await parent();
    });

    planningFieldServiceModels.PlanningSlot._views.search = `
        <search>
            <filter string="Start Date" name="start_datetime" date="start_datetime"/>
        </search>`;

    planningFieldServiceModels.PlanningSlot._views.map = `
        <map res_partner="partner_id" default_order="sequence, start_datetime, id" routing="ordered" default_group_by="resource_ids" js_class="planning_field_service_map_timeline">
            <field name="partner_id" string="Customer"/>
            <field name="resource_ids" string="Resources"/>
            <field name="start_datetime" string="Date"/>
        </map>`;

    planningFieldServiceModels.PlanningSlot._views.gantt = `
        <gantt js_class="planning_gantt"
            date_start="start_datetime"
            date_stop="end_datetime"
            default_group_by="resource_ids"
            color="color"
            plan="false"
            string="Schedule"
            precision="{'day': 'hour:quarter'}"
            pill_label="True"
            schedule="1"
            progress_bar="resource_ids"
        >
            <field name="resource_ids"/>
            <field name="user_ids"/>
            <field name="can_edit"/>
            <field name="partner_id" invisible="1"/>
        </gantt>`;

    planningFieldServiceModels.PlanningSlot._records = [
        {
            id: 1,
            name: "Onsite Repair",
            partner_id: 520,
            resource_ids: [1],
            start_datetime: "2026-01-04 08:00:00",
            end_datetime: "2026-01-04 10:00:00",
        },
        {
            id: 2,
            name: "Network Install",
            partner_id: 520,
            resource_ids: [2],
            start_datetime: "2026-01-04 11:00:00",
            end_datetime: "2026-01-04 13:00:00",
        },
    ];
});

test("the gantt sub-view is hidden when the 'Today' relative date filter isn't active", async () => {
    let getGanttDataCount = 0;
    onRpc("get_gantt_data", () => {
        getGanttDataCount++;
    });

    await mountMapTimeline();

    expect(".o_gantt_view").toHaveCount(1, {
        message: "the gantt sub-view should render while the 'Today' filter is active",
    });
    expect(getGanttDataCount).toBe(1);

    await click(".o_searchview_facet:contains('Start Date') .o_facet_remove");
    await animationFrame();

    expect(".o_gantt_view").toHaveCount(0, {
        message: "removing the filter should hide the gantt sub-view",
    });
    expect(".o_map_timeline_gantt_pane").toHaveCount(0);
    expect(".o_map_timeline_resize").toHaveCount(0, {
        message: "the resize handle only makes sense between two panes",
    });
    expect(getGanttDataCount).toBe(1, {
        message: "the gantt sub-view shouldn't load data again once it's hidden",
    });
    expect(".o_map_timeline_map_pane.h-100.mh-100").toHaveCount(1, {
        message: "the map should reclaim the full height instead of leaving a gap",
    });
});

test("the map and its nested gantt sub-view both render and each load their own data", async () => {
    let webSearchReadCount = 0;
    let getGanttDataCount = 0;
    onRpc("web_search_read", ({ model }) => {
        if (model !== "planning.slot") {
            return;
        }
        webSearchReadCount++;
        expect.step("web_search_read");
    });
    onRpc("get_gantt_data", () => {
        getGanttDataCount++;
        expect.step("get_gantt_data");
    });

    await mountMapTimeline();

    expect("div.o_map_view").toBeVisible({ message: "the map view should be mounted" });
    expect(".o-map-renderer--container").toHaveCount(1, {
        message: "the leaflet map should be rendered",
    });
    expect(".o_gantt_view").toHaveCount(1, { message: "the nested gantt view should be rendered" });

    expect(webSearchReadCount).toBe(2, {
        message:
            "the map should load once initially, then the gantt side panel should load its own data independently",
    });
    expect(getGanttDataCount).toBe(1, {
        message: "the gantt sub-view should load its data exactly once",
    });
    expect.verifySteps(["web_search_read", "get_gantt_data", "web_search_read"], {
        message:
            "the map loads first, the gantt sub-view loads independently right after, then the gantt side panel should load",
    });
});

test("the same slots are displayed in the map pin list and in the gantt sub-view", async () => {
    const { name: resource1Name } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 1
    );
    const { name: resource2Name } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 2
    );

    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Internal Maintenance",
        resource_ids: [1],
        start_datetime: "2026-01-04 14:00:00",
        end_datetime: "2026-01-04 15:00:00",
    });

    await mountMapTimeline();

    const mapSlotNames = queryAllTexts(
        ".o-map-renderer--pin-list-details .o_row_task_title"
    ).sort();
    const ganttSlotNames = queryAllTexts(".o_gantt_pill_title").sort();

    expect(mapSlotNames).toEqual(["Network Install", "Onsite Repair"], {
        message: "only the customer-linked slots should have a pin on the map",
    });
    expect(ganttSlotNames).toEqual(["Internal Maintenance", "Network Install", "Onsite Repair"], {
        message:
            "the gantt sub-view should also display the customer-less slot, which the map can't",
    });

    expect(
        `.o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('${resource1Name}')) li:contains('Onsite Repair')`
    ).toHaveCount(1, { message: "Onsite Repair's pin should be under resource 1's map group" });
    expect(
        `.o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('${resource2Name}')) li:contains('Network Install')`
    ).toHaveCount(1, { message: "Network Install's pin should be under resource 2's map group" });
});

test("open shift is displayed in the gantt and grouped under 'Open Shifts' on the map", async () => {
    planningFieldServiceModels.PlanningSlot._fields.resource_ids.falsy_value_label = "Open Shifts";

    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Cleaning",
        partner_id: 520,
        resource_ids: [],
        start_datetime: "2026-01-04 16:00:00",
        end_datetime: "2026-01-04 18:00:00",
    });

    await mountMapTimeline();

    expect(queryAllTexts(".o_gantt_row_title_label")).toInclude("Open Shifts");
    expect(".o_gantt_pill_title:contains('Cleaning')").toHaveCount(1, {
        message: "an open shift has no resource but is still scheduled, so the gantt shows it",
    });

    expect(".o-map-renderer--pin-list-group-header:contains('Open Shifts')").toHaveCount(1, {
        message: "the map should have a dedicated 'Open Shifts' pin-list group",
    });
    expect(
        ".o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('Open Shifts')) li:contains('Cleaning')"
    ).toHaveCount(1, {
        message: "the open shift's pin should be nested under the 'Open Shifts' group",
    });
});

test("unscheduled shift is displayed in the gantt's side panel and grouped under 'Shifts to Schedule' on the map", async () => {
    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Repair",
        partner_id: 520,
        resource_ids: [1],
        start_datetime: false,
        end_datetime: false,
    });

    await mountMapTimeline();

    expect(".o_gantt_sidepanel .o_event_to_schedule_draggable").toHaveText("Repair", {
        message: "the unscheduled shift should be listed in the gantt's side panel",
    });

    expect(".o-map-renderer--pin-list-group-header:contains('Shifts to Schedule')").toHaveCount(1, {
        message: "the map should have a dedicated 'Shifts to Schedule' pin-list group",
    });
    expect(
        ".o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('Shifts to Schedule')) li:contains('Repair')"
    ).toHaveCount(1, {
        message:
            "the unscheduled shift's pin should be nested under the 'Shifts to Schedule' group",
    });
});

test("the map and gantt panes have the expected default sizes, and the resize handle works", async () => {
    await mountMapTimeline();

    const mapPane = queryFirst(".o_map_timeline_map_pane");
    const ganttPane = queryFirst(".o_map_timeline_gantt_pane");

    const initialMapHeight = mapPane.offsetHeight;
    const initialGanttHeight = ganttPane.offsetHeight;

    expect(initialMapHeight).toBeGreaterThan(0);
    expect(initialGanttHeight).toBeGreaterThan(0);
    expect(initialMapHeight / (initialMapHeight + initialGanttHeight)).toBeWithin(0.65, 0.75, {
        message: "the map pane should default to roughly 70% of the shared height",
    });

    const resizeHandle = queryFirst(".o_map_timeline_resize");
    const handleRect = resizeHandle.getBoundingClientRect();

    const { moveTo, drop } = await drag(resizeHandle);
    await moveTo(resizeHandle, { position: { y: handleRect.y + 20 } });
    await animationFrame();
    await moveTo(resizeHandle, { position: { y: handleRect.y + 120 } });
    await animationFrame();

    expect(mapPane.offsetHeight).toBeGreaterThan(initialMapHeight, {
        message: "dragging the resize handle down should grow the map pane",
    });
    expect(ganttPane.offsetHeight).toBeLessThan(initialGanttHeight, {
        message: "the gantt pane should shrink accordingly, since the shared height is fixed",
    });

    await drop();
});

test("rescheduling a gantt pill reschedules it and reloads the map", async () => {
    const { name: resource1Name } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 1
    );
    planningFieldServiceModels.PlanningSlot._fields.resource_ids.falsy_value_label = "Open Shifts";
    const onsiteRepair = planningFieldServiceModels.PlanningSlot._records.find(
        (record) => record.id === 1
    );
    onsiteRepair.can_edit = true;

    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Cleaning",
        resource_ids: [],
        start_datetime: "2026-01-04 08:00:00",
        end_datetime: "2026-01-04 10:00:00",
    });

    onRpc(({ method, model }) => {
        if (
            model === "planning.slot" &&
            ["write", "get_gantt_data", "web_search_read"].includes(method)
        ) {
            expect.step(method);
        }
    });
    onRpc("write", ({ args }) => {
        expect(args[0]).toEqual([1], { message: "the dragged slot should be the one written" });
        expect(args[1]).toEqual(
            { resource_ids: false },
            { message: "dropping onto the 'Open Shifts' row should unassign the resource" }
        );
    });

    await mountMapTimeline();
    expect.verifySteps(["web_search_read", "get_gantt_data", "web_search_read"], {
        message: "check the initial map/gantt/side-panel loads",
    });

    expect(".o_gantt_pill_wrapper:contains('Onsite Repair') .o_gantt_lock").toHaveCount(0, {
        message: "the slot must be editable for the drag below to be allowed",
    });
    expect(queryAllTexts(".o_gantt_row_title_label")).toInclude("Open Shifts");
    expect(".o-map-renderer--pin-list-group-header:contains('Open Shifts')").toHaveCount(0, {
        message: "the only open shift so far has no customer, so it can't show up on the map yet",
    });
    expect(
        `.o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('${resource1Name}')) li:contains('Onsite Repair')`
    ).toHaveCount(1);

    const { drop } = await dragPill("Onsite Repair");
    await drop({ pill: "Cleaning" });

    // To fix: we should avoid the two last rpc calls, they are triggered after this flow:
    // The gantt reloads -> map reloads -> notify/re-render of <MapTimelineGanttController  t-props="this.ganttProps"/> -> onWillUpdateProps triggered (const loadProm = load(nextProps)) -> gantt reloads
    expect.verifySteps(
        [
            "write",
            "get_gantt_data",
            "web_search_read",
            "web_search_read",
            "get_gantt_data",
            "web_search_read",
        ],
        {
            message:
                "the write reschedules the gantt (which reloads the gantt (with the side panel) and finally reloads the map",
        }
    );

    expect(`.o-map-renderer--pin-list-group-header:contains('${resource1Name}')`).toHaveCount(0, {
        message: "resource 1 has no more shifts, so its map group should disappear",
    });
    expect(queryAllTexts(".o_gantt_row_title_label")).not.toInclude(resource1Name, {
        message: "and its gantt row should disappear too",
    });
    expect(".o-map-renderer--pin-list-group-header:contains('Open Shifts')").toHaveCount(1, {
        message:
            "Onsite Repair now has a customer and is an open shift, so the group should appear",
    });
    expect(
        ".o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('Open Shifts')) li"
    ).toHaveCount(1, {
        message: "Cleaning still has no customer and stays invisible on the map",
    });
    expect(
        ".o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('Open Shifts')) li:contains('Onsite Repair')"
    ).toHaveCount(1);
    expect(".o_gantt_pill_title:contains('Onsite Repair')").toHaveCount(1, {
        message: "the gantt should also reflect the new row for the rescheduled pill",
    });
});

test("creating a shift from an empty gantt cell shows it on the map, and deleting it removes it", async () => {
    const { name: resource1Name } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 1
    );

    onRpc(({ method, model }) => {
        if (
            model === "planning.slot" &&
            ["web_save", "unlink", "get_gantt_data", "web_search_read"].includes(method)
        ) {
            expect.step(method);
        }
    });

    await mountMapTimeline();
    expect.verifySteps(["web_search_read", "get_gantt_data", "web_search_read"], {
        message: "check the initial map/gantt/side-panel loads",
    });

    await clickCell("14", "", resource1Name);
    await waitFor(".o_dialog .o_form_view");

    await click(".o_dialog .o_field_widget[name=name] input");
    await edit("New Shift");
    await click(".o_dialog .o_field_widget[name=partner_id] input");
    await edit("Foo");
    await animationFrame();
    await click(".o_dialog .o-autocomplete--dropdown-item:contains('Foo')");
    await click(".o_dialog .o_form_button_save");
    await animationFrame();

    // To fix: we should avoid the two last rpc calls, they are triggered after this flow:
    // The gantt reloads -> map reloads -> notify/re-render of <MapTimelineGanttController  t-props="this.ganttProps"/> -> onWillUpdateProps triggered (const loadProm = load(nextProps)) -> gantt reloads
    expect.verifySteps(
        [
            "web_save",
            "get_gantt_data",
            "web_search_read",
            "web_search_read",
            "get_gantt_data",
            "web_search_read",
        ],
        {
            message:
                "the save reschedules the gantt (which reloads its own side panel too) and in turn reloads the map",
        }
    );

    expect(".o_gantt_pill_title:contains('New Shift')").toHaveCount(1, {
        message: "the new shift should show up in the gantt, under resource 1's row",
    });
    expect(
        `.o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('${resource1Name}')) li:contains('New Shift')`
    ).toHaveCount(1, { message: "and its pin should show up under resource 1's map group" });

    await click(".o_gantt_pill:contains('New Shift')");
    await runAllTimers();
    await waitFor(".o_popover");
    await click(".o_popover .btn-delete");
    await animationFrame();
    await click(".modal button:contains('Delete')");
    await animationFrame();

    // To fix: we should avoid the two last rpc calls, they are triggered after this flow:
    // The gantt reloads -> map reloads -> notify/re-render of <MapTimelineGanttController  t-props="this.ganttProps"/> -> onWillUpdateProps triggered (const loadProm = load(nextProps)) -> gantt reloads
    expect.verifySteps(
        [
            "unlink",
            "get_gantt_data",
            "web_search_read",
            "web_search_read",
            "get_gantt_data",
            "web_search_read",
        ],
        {
            message: "deleting it triggers the same gantt + map reload chain as creating it",
        }
    );

    expect(".o_gantt_pill_title:contains('New Shift')").toHaveCount(0, {
        message: "the shift should be gone from the gantt",
    });
    expect(".o-map-renderer--pin-list-details li:contains('New Shift')").toHaveCount(0, {
        message: "and its pin should be gone from the map too",
    });
});

test("shifting the search view's date filter navigates the gantt sub-view", async () => {
    const ganttCalls = [];
    onRpc("get_gantt_data", ({ kwargs }) => {
        ganttCalls.push({
            domain: kwargs.domain,
            start_date: kwargs.start_date,
            stop_date: kwargs.stop_date,
        });
    });

    await mountMapTimeline();

    expect(ganttCalls.length).toBe(1, { message: "the gantt should load once on mount" });

    await click("button[aria-label='Next period']");
    await animationFrame();

    expect(ganttCalls.length).toBe(2, {
        message: "shifting the date filter should trigger the gantt to reload",
    });
    const [initialCall, nextCall] = ganttCalls;
    expect(JSON.stringify(nextCall.domain)).not.toBe(JSON.stringify(initialCall.domain), {
        message: "the search domain should reflect the shifted filter",
    });
    expect(nextCall.start_date).not.toBe(initialCall.start_date, {
        message: "the gantt's own visible window should also move to follow the filter",
    });
    expect(nextCall.stop_date).not.toBe(initialCall.stop_date);
});

test("the map and the gantt stay in sync with the date filter, and both always show unscheduled shifts", async () => {
    // Same-day slots (already covered by the shared fixtures): Onsite Repair,
    // Network Install. Add their next-day counterparts, an open shift for
    // each day, and one unscheduled shift that should never be filtered out.
    planningFieldServiceModels.PlanningSlot._records.push(
        {
            id: 3,
            name: "Tomorrow Repair",
            partner_id: 520,
            resource_ids: [1],
            start_datetime: "2026-01-05 08:00:00",
            end_datetime: "2026-01-05 10:00:00",
        },
        {
            id: 4,
            name: "Tomorrow Install",
            partner_id: 520,
            resource_ids: [2],
            start_datetime: "2026-01-05 11:00:00",
            end_datetime: "2026-01-05 13:00:00",
        },
        {
            id: 5,
            name: "Today Open Shift",
            partner_id: 520,
            resource_ids: [],
            start_datetime: "2026-01-04 16:00:00",
            end_datetime: "2026-01-04 18:00:00",
        },
        {
            id: 6,
            name: "Tomorrow Open Shift",
            partner_id: 520,
            resource_ids: [],
            start_datetime: "2026-01-05 16:00:00",
            end_datetime: "2026-01-05 18:00:00",
        },
        {
            id: 7,
            name: "Unscheduled Repair",
            partner_id: 520,
            resource_ids: [1],
            start_datetime: false,
            end_datetime: false,
        }
    );

    await mountMapTimeline();
    const mapModel = (await findComponentInAnyRoot((c) => c instanceof MapController)).model;
    const ganttModel = (await findComponentInAnyRoot((c) => c instanceof GanttController)).model;
    const names = (records) => records.map((r) => r.display_name).sort();

    expect(names(mapModel.data.records)).toEqual(
        ["Network Install", "Onsite Repair", "Today Open Shift", "Unscheduled Repair"].sort(),
        {
            message:
                "the map should show today's scheduled and open shifts, plus the unscheduled one",
        }
    );
    expect(names(ganttModel.data.records)).toEqual(
        ["Network Install", "Onsite Repair", "Today Open Shift"].sort(),
        { message: "the gantt's main area mirrors the map for today, minus the unscheduled shift" }
    );
    expect(names(ganttModel.data.eventsToSchedule.records)).toEqual(["Unscheduled Repair"], {
        message: "the gantt shows the unscheduled shift in its own side panel instead",
    });

    await click("button[aria-label='Next period']");
    await animationFrame();

    expect(names(mapModel.data.records)).toEqual(
        ["Tomorrow Install", "Tomorrow Repair", "Tomorrow Open Shift", "Unscheduled Repair"].sort(),
        {
            message:
                "shifting to tomorrow should swap in tomorrow's slots, but keep the unscheduled one",
        }
    );
    expect(names(ganttModel.data.records)).toEqual(
        ["Tomorrow Install", "Tomorrow Repair", "Tomorrow Open Shift"].sort(),
        { message: "the gantt should follow the same shift" }
    );
    expect(names(ganttModel.data.eventsToSchedule.records)).toEqual(["Unscheduled Repair"], {
        message: "the unscheduled shift should still be shown, regardless of the date filter",
    });
});

test("folding a resource group on the map also folds that resource's row in the gantt sub-view", async () => {
    const { name: resourceName } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 1
    );

    await mountMapTimeline();

    expect(queryAllTexts(".o_gantt_row_title_label")).toInclude(resourceName);
    expect(".o_gantt_pill_title:contains('Onsite Repair')").toHaveCount(1);

    await click(`.o-map-renderer--pin-list-group-header:contains('${resourceName}')`);
    await animationFrame();

    expect(queryAllTexts(".o_gantt_row_title_label")).not.toInclude(resourceName, {
        message: "collapsing the resource's pin group should hide its row in the gantt",
    });
    expect(".o_gantt_pill_title:contains('Onsite Repair')").toHaveCount(0, {
        message: "the corresponding pill should no longer be rendered",
    });
    expect(".o_gantt_pill_title:contains('Network Install')").toHaveCount(1, {
        message: "the other resource's row should be unaffected",
    });
});

test("folding the 'Open Shifts' group on the map hides the open shifts row in the gantt sub-view", async () => {
    planningFieldServiceModels.PlanningSlot._fields.resource_ids.falsy_value_label = "Open Shifts";

    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Cleaning",
        partner_id: 520,
        resource_ids: [],
        start_datetime: "2026-01-04 16:00:00",
        end_datetime: "2026-01-04 18:00:00",
    });

    await mountMapTimeline();

    expect(queryAllTexts(".o_gantt_row_title_label")).toInclude("Open Shifts");
    expect(".o_gantt_pill_title:contains('Cleaning')").toHaveCount(1);

    await click(".o-map-renderer--pin-list-group-header:contains('Open Shifts')");
    await animationFrame();

    expect(queryAllTexts(".o_gantt_row_title_label")).not.toInclude("Open Shifts", {
        message:
            "collapsing the 'Open Shifts' pin group should hide the open shifts row in the gantt",
    });
    expect(".o_gantt_pill_title:contains('Cleaning')").toHaveCount(0, {
        message: "the corresponding pill should no longer be rendered",
    });
    expect(".o_gantt_pill_title:contains('Onsite Repair')").toHaveCount(1, {
        message: "the resource rows should be unaffected",
    });
});

test("folding the 'Shifts to Schedule' group on the map hides the gantt sub-view's side panel", async () => {
    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Repair",
        partner_id: 520,
        resource_ids: [1],
        start_datetime: false,
        end_datetime: false,
    });

    await mountMapTimeline();

    expect(".o_gantt_sidepanel").toHaveCount(1);
    expect(".o_gantt_sidepanel .o_event_to_schedule_draggable").toHaveText("Repair");

    await click(".o-map-renderer--pin-list-group-header:contains('Shifts to Schedule')");
    await animationFrame();

    expect(".o_gantt_sidepanel").toHaveCount(0, {
        message: "collapsing the 'Shifts to Schedule' pin group should hide the gantt's side panel",
    });
    expect(".o_gantt_pill_title:contains('Onsite Repair')").toHaveCount(1, {
        message: "the main gantt area should be unaffected",
    });
});

test("hovering a slot in the map pin list highlights the matching pill in the gantt sub-view", async () => {
    const { name: resourceName } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 1
    );

    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Follow-up Repair",
        partner_id: 520,
        resource_ids: [1],
        start_datetime: "2026-01-04 15:00:00",
        end_datetime: "2026-01-04 16:00:00",
    });

    await mountMapTimeline();

    expect(".o_gantt_pill_wrapper.highlight").toHaveCount(0);
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0);

    await hover("li:contains('Onsite Repair')");
    await animationFrame();

    expect(".o_gantt_pill_wrapper.highlight").toHaveCount(1, {
        message: "hovering the pin-list entry should highlight the matching gantt pill",
    });
    expect(".o_gantt_pill_wrapper.highlight .o_gantt_pill_title").toHaveText("Onsite Repair");
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(1, {
        message: "hovering the pin-list entry should also highlight the matching pin on the map",
    });

    await hover(document.body);
    await animationFrame();

    expect(".o_gantt_pill_wrapper.highlight").toHaveCount(0, {
        message: "moving away should remove the highlight",
    });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0, {
        message: "moving away should remove the marker highlight too",
    });

    await hover(`.o-map-renderer--pin-list-group-header:contains('${resourceName}')`);
    await animationFrame();

    expect(".o_gantt_pill_wrapper.highlight").toHaveCount(2, {
        message:
            "hovering the resource's group header should highlight every shift of that resource",
    });
    expect(queryAllTexts(".o_gantt_pill_wrapper.highlight .o_gantt_pill_title").sort()).toEqual([
        "Follow-up Repair",
        "Onsite Repair",
    ]);
    expect(
        ".o_gantt_pill_wrapper.highlight .o_gantt_pill_title:contains('Network Install')"
    ).toHaveCount(0, { message: "the other resource's shift should be unaffected" });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(1, {
        message:
            "hovering the resource's group header should also highlight every pin of that resource on the map. But as they are located at the same address, only one marker is highlighted",
    });

    await hover(document.body);
    await animationFrame();

    expect(".o_gantt_pill_wrapper.highlight").toHaveCount(0, {
        message: "moving away from the group header should also remove the highlight",
    });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0, {
        message: "moving away from the group header should also remove the marker highlight",
    });
});

test("hovering a pill in the gantt sub-view highlights the matching pin on the map", async () => {
    await mountMapTimeline();

    expect("li:contains('Onsite Repair').o_map_pin_hover").toHaveCount(0);
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0);

    await hover(".o_gantt_pill_wrapper:contains('Onsite Repair')");
    await animationFrame();

    expect("li:contains('Onsite Repair').o_map_pin_hover").toHaveCount(1, {
        message: "hovering the gantt pill should highlight the matching pin-list entry",
    });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(1, {
        message: "hovering the gantt pill should also highlight the matching leaflet marker",
    });
    expect("li:contains('Network Install').o_map_pin_hover").toHaveCount(0, {
        message: "the other slot's pin should be unaffected",
    });

    await hover(document.body);
    await animationFrame();

    expect("li:contains('Onsite Repair').o_map_pin_hover").toHaveCount(0, {
        message: "moving away should remove the pin-list highlight",
    });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0, {
        message: "moving away should remove the marker highlight too",
    });
});

test("hovering a shift in the gantt sub-view's side panel highlights the matching pin on the map", async () => {
    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Repair",
        partner_id: 520,
        resource_ids: [1],
        start_datetime: false,
        end_datetime: false,
    });

    await mountMapTimeline();

    expect("li:contains('Repair').o_map_pin_hover").toHaveCount(0);
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0);

    await hover(".o_gantt_sidepanel .o_event_to_schedule_draggable:contains('Repair')");
    await animationFrame();

    expect("li:contains('Repair').o_map_pin_hover").toHaveCount(1, {
        message:
            "hovering the unscheduled shift in the gantt's side panel should highlight the matching pin-list entry, under the 'Shifts to Schedule' group",
    });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(1, {
        message:
            "hovering the unscheduled shift in the gantt's side panel should also highlight the matching pin on the map",
    });
    expect("li:contains('Onsite Repair').o_map_pin_hover").toHaveCount(0, {
        message: "the other slots' pins should be unaffected",
    });

    await hover(document.body);
    await animationFrame();

    expect("li:contains('Repair').o_map_pin_hover").toHaveCount(0, {
        message: "moving away should remove the pin-list highlight",
    });
    expect(".leaflet-marker-icon.o_map_marker_hover").toHaveCount(0, {
        message: "moving away should remove the marker highlight too",
    });
});

test("hovering an unscheduled shift's pin in the map pin list highlights the matching entry in the gantt sub-view's side panel", async () => {
    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Repair",
        partner_id: 520,
        resource_ids: [1],
        start_datetime: false,
        end_datetime: false,
    });

    await mountMapTimeline();

    const sidePanelEntry = ".o_gantt_sidepanel .o_event_to_schedule_draggable:contains('Repair')";
    const pinListEntry =
        ".o-map-renderer--pin-list-group:has(.o-map-renderer--pin-list-group-header:contains('Shifts to Schedule')) li:contains('Repair')";

    expect(`${sidePanelEntry}.o_map_timeline_side_panel_hover`).toHaveCount(0);

    await hover(pinListEntry);
    await animationFrame();

    expect(`${sidePanelEntry}.o_map_timeline_side_panel_hover`).toHaveCount(1, {
        message:
            "hovering the unscheduled shift's pin-list entry should highlight the matching shift in the gantt sub-view's side panel",
    });

    await hover(document.body);
    await animationFrame();

    expect(`${sidePanelEntry}.o_map_timeline_side_panel_hover`).toHaveCount(0, {
        message: "moving away should remove the side panel highlight",
    });
});

test("hovering a resource's group header on the map reveals its pins' stop number", async () => {
    const { name: resourceName } = planningFieldServiceModels.ResourceResource._records.find(
        (resource) => resource.id === 1
    );

    planningFieldServiceModels.ResPartner._records.push({
        id: 521,
        name: "Auber",
        partner_latitude: 51.0,
        partner_longitude: 5.0,
    });
    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Follow-up Repair",
        partner_id: 521,
        resource_ids: [1],
        start_datetime: "2026-01-04 14:00:00",
        end_datetime: "2026-01-04 15:00:00",
    });

    await mountMapTimeline();

    expect(".o_map_marker_pin:visible").toHaveCount(3, {
        message: "all three pins should show their normal icon by default",
    });
    expect(".o_map_marker_stop_numbering_pin:visible").toHaveCount(0, {
        message: "no stop number should be shown while no group is hovered",
    });

    await hover(`.o-map-renderer--pin-list-group-header:contains('${resourceName}')`);
    await animationFrame();

    expect(".leaflet-marker-icon.o_map_marker_group_hover").toHaveCount(2, {
        message: "hovering the group header should mark both of that resource's pins for numbering",
    });
    expect(".o_map_marker_pin:visible").toHaveCount(1, {
        message: "the other resource's pin should keep showing its normal icon",
    });
    expect(".o_map_marker_stop_numbering_pin:visible").toHaveCount(2, {
        message: "both of the hovered resource's pins should reveal their stop number",
    });
    expect(queryAllTexts(".o_map_marker_stop_numbering_pin:visible").sort()).toEqual(["1", "2"], {
        message: "Onsite Repair (08:00) is the first stop, Follow-up Repair (14:00) the second",
    });

    await hover(document.body);
    await animationFrame();

    expect(".o_map_marker_pin:visible").toHaveCount(3, {
        message: "moving away should restore every pin's normal icon",
    });
    expect(".o_map_marker_stop_numbering_pin:visible").toHaveCount(0, {
        message: "moving away should hide the stop numbers again",
    });
});

test("a material resource's color matches across the gantt row header, the map pin, and the map pin-list", async () => {
    planningFieldServiceModels.ResPartner._records.push({
        id: 521,
        name: "Bar",
        partner_latitude: 51.0,
        partner_longitude: 5.0,
    });
    planningFieldServiceModels.ResourceResource._records.push({
        id: 3,
        name: "Generator",
        resource_type: "material",
        color: 10,
    });
    planningFieldServiceModels.PlanningSlot._records.push({
        id: 3,
        name: "Generator Rental",
        partner_id: 521,
        resource_ids: [3],
        start_datetime: "2026-01-04 09:00:00",
        end_datetime: "2026-01-04 12:00:00",
    });

    onRpc("get_gantt_data", async ({ parent }) => {
        const result = await parent();
        result.progress_bars.resource_ids[3] = {
            is_material_resource: true,
            resource_color: 10,
        };
        return result;
    });

    await mountMapTimeline();

    const rgbOnly = (color) => color.match(/\d+(?:, ?\d+){2}/)[0];

    const ganttColor = rgbOnly(
        getComputedStyle(queryOne(".o_gantt_row_title .o_avatar .o_material_resource"))
            .backgroundColor
    );

    await click(".o-map-renderer--pin-list-group-header:contains('Generator')");
    await animationFrame();

    const markerColor = rgbOnly(
        queryOne(".leaflet-marker-icon:nth-of-type(3) .o_map_marker_pin path[fill]").getAttribute(
            "fill"
        )
    );
    const pinListColor = rgbOnly(
        queryOne(
            ".o-map-renderer--pin-list-group-header:contains('Generator') .o-map-renderer--pin-list-group-svg path[fill]"
        ).getAttribute("fill")
    );

    expect(markerColor).toBe(ganttColor, {
        message: "the map pin's color should match the gantt row header avatar's color",
    });
    expect(pinListColor).toBe(ganttColor, {
        message: "the map pin-list's color should match the gantt row header avatar's color",
    });
});
