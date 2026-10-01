import { browser } from "@web/core/browser/browser";
import { beforeEach, expect, test } from "@odoo/hoot";
import {
    advanceTime,
    animationFrame,
    queryAll,
    queryAllTexts,
    queryFirst,
    runAllTimers,
    waitFor,
    waitForNone,
} from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { startServer } from "@mail/../tests/mail_test_helpers";
import {
    contains,
    findComponent,
    isSmall,
    getService,
    mountView,
    mountWebClient,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { session } from "@web/session";
import { MapRenderer } from "@web_map/map_view/map_renderer";

import {
    definePlanningFieldServiceModels,
    planningFieldServiceModels,
} from "./planning_field_service_mock_models";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";
import { PlanningFieldServiceLiveMapModel } from "@planning_field_service/views/planning_field_service_live_map/planning_field_service_live_map_model";

const MAP_BOX_TOKEN = "token";
const LIVE_LOCATIONS = {
    "(50.3, 4.65)": {
        street: "Sweat street",
        house_number: "123",
        city: "Nice city",
        zip: "9999",
        state: "Province 2",
        country: "Best country",
    },
    "(50.26, 4.91)": {
        street: "Rue du Blé",
        house_number: "17",
        city: "Liège",
        zip: "5556",
        state: "Liège",
        country: "Belgium",
    },
    "(50.45, 4.36)": {
        street: "Some road",
        house_number: "891",
        city: "Great City",
        zip: "0000",
        state: "Some province",
        country: "Somewhere",
    },
};

async function verifyMarkerPopup(markerEl, expectedTexts) {
    expect("div.leaflet-popup").toHaveCount(0, {
        message: "The user marker popup information should not be opened by default",
    });

    await contains(markerEl).hover();
    await animationFrame();
    expect("div.leaflet-popup").toHaveCount(1, {
        message: "The user marker popup information should be opened when hovering the user marker",
    });

    const root = "div.leaflet-popup-content";
    expect(queryAll("img", { root })).toHaveCount(1, {
        message: "The user avatar should be visible on the popup",
    });
    expect(queryAllTexts("div.flex-column div", { root })).toEqual(expectedTexts);

    await contains("div.o_control_panel").hover();
    await advanceTime(500); // wait for the closing animation to finish
    expect("div.leaflet-popup").toHaveCount(0, {
        message: "The user marker popup information should be closed on exit",
    });
}

definePlanningFieldServiceModels();

beforeEach(() => {
    mockDate("2026-01-04 12:00:00", 0);
    planningFieldServiceModels.PlanningSlot._views.map = `
        <map res_partner="partner_id" js_class="planning_field_service_live_map" routing="ordered">
            <field name="resource_ids" invisible="1"/>
            <field name="start_datetime" invisible="1"/>
            <field name="end_datetime" invisible="1"/>
        </map>`;
    patchWithCleanup(Geolocation.prototype, {
        async geolocatePartners(partners) {
            partners.partner_latitude = 50.0;
            partners.partner_longitude = 5.0;
            return true;
        },
        async _fetchAddressFromCoordinatesOSM(lat, lon) {
            return LIVE_LOCATIONS[`(${lat}, ${lon})`];
        },
        async _fetchAddressFromCoordinatesMB(lat, lon) {
            return LIVE_LOCATIONS[`(${lat}, ${lon})`];
        },
    });
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
});

test.tags("desktop");
test("live map (osm): captures user's live location, displays a pin for the user, and opens a popup when hovered", async () => {
    const pyEnv = await startServer();
    pyEnv["resource.resource"].write([1], {
        live_latitude: 50.26,
        live_longitude: 4.91,
        live_location_last_update: "2026-01-04 11:59:00",
    });

    await mountView({
        type: "map",
        resModel: "planning.slot",
    });

    expect("div.o_map_view").toBeVisible({
        message: "The map should be visible",
    });
    expect("div.o_planning_field_service_live_map_view").toBeVisible({
        message: "The live map view should be visible",
    });

    expect("div.leaflet-marker-icon").toHaveCount(3, {
        message:
            "There should be 3 markers on the map (current user location, one partner, one user)",
    });

    const userMarker = queryAll("div.leaflet-marker-icon:has(img)");
    expect(userMarker).toHaveCount(1, {
        message: "There should be one user marker on the map",
    });
    await verifyMarkerPopup(userMarker, [
        "Mitchell Admin",
        "Rue du Blé, 17\n5556 Liège",
        "1 minute ago",
    ]);
});

test.tags("desktop");
test("live map (mb): shows multiple user markers", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    const pyEnv = await startServer();
    const resources = pyEnv["resource.resource"].create([
        {
            name: "Technician 1",
            live_latitude: 50.3,
            live_longitude: 4.65,
            live_location_last_update: "2026-01-04 12:00:00",
        },
        {
            name: "Technician 2",
            live_latitude: 50.26,
            live_longitude: 4.91,
            live_location_last_update: "2026-01-04 06:24:18",
        },
        {
            name: "Technician 3",
            live_latitude: 50.45,
            live_longitude: 4.36,
            live_location_last_update: "2026-01-04 11:00:00",
        },
    ]);
    pyEnv["planning.slot"].create([
        {
            name: "Intervention",
            partner_id: 1,
            resource_ids: resources,
            start_datetime: "2026-01-04 15:00:00",
            end_datetime: "2026-01-04 16:00:00",
        },
    ]);

    await mountView({
        type: "map",
        resModel: "planning.slot",
    });

    expect("div.o_map_view").toBeVisible({
        message: "The map should be visible",
    });
    expect("div.o_planning_field_service_live_map_view").toBeVisible({
        message: "The live map view should be visible",
    });

    expect("div.leaflet-marker-icon").toHaveCount(5, {
        message:
            "There should be 5 markers on the map (current user location, one partner, and 3 users)",
    });

    const userMarkers = queryAll("div.leaflet-marker-icon:has(img)");
    expect(userMarkers).toHaveCount(3, {
        message: "There should be 3 user markers on the map",
    });

    await verifyMarkerPopup(userMarkers[0], [
        "Technician 1",
        "Sweat street, 123\n9999 Nice city",
        "Just now",
    ]);
    await verifyMarkerPopup(userMarkers[1], [
        "Technician 2",
        "Rue du Blé, 17\n5556 Liège",
        "5 hours ago",
    ]);
    await verifyMarkerPopup(userMarkers[2], [
        "Technician 3",
        "Some road, 891\n0000 Great City",
        "1 hour ago",
    ]);
});

test("live map (osm): technicians appear one by one as their address is progressively resolved", async () => {
    patchWithCleanup(Geolocation, {
        OSM_COORDINATE_FETCH_DELAY: 1000,
    });

    const pyEnv = await startServer();
    const [resource1, resource2] = pyEnv["resource.resource"].create([
        {
            name: "Technician 1",
            live_latitude: 50.3,
            live_longitude: 4.65,
            live_location_last_update: "2026-01-04 12:00:00",
        },
        {
            name: "Technician 2",
            live_latitude: 50.26,
            live_longitude: 4.91,
            live_location_last_update: "2026-01-04 06:24:18",
        },
    ]);
    pyEnv["planning.slot"].create({
        name: "Intervention",
        partner_id: 1,
        resource_ids: [resource1, resource2],
        start_datetime: "2026-01-04 15:00:00",
        end_datetime: "2026-01-04 16:00:00",
    });

    await mountView({
        type: "map",
        resModel: "planning.slot",
    });

    expect("div.leaflet-marker-icon:has(img)").toHaveCount(1, {
        message: "Only the first technician's address has resolved so far",
    });

    await runAllTimers();
    await waitFor("div.leaflet-marker-icon:has(img)", { count: 2 });

    expect("div.leaflet-marker-icon:has(img)").toHaveCount(2, {
        message: "The second technician should now be shown too, once its address resolved",
    });
});

test.tags("desktop");
test("live map (mb): does not show user marker if its resource is collapsed", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    const pyEnv = await startServer();
    const [partner1, partner2] = pyEnv["res.partner"].create([
        {
            name: "Foo",
            partner_latitude: 50.2,
            partner_longitude: 4.55,
            contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
        },
        {
            name: "Foo 2",
            partner_latitude: 50.3,
            partner_longitude: 4.52,
            contact_address_complete: "Chaussée de Namur 312, 1367, Ramillies",
        },
    ]);
    const [resource1, resource2, resource3] = pyEnv["resource.resource"].create([
        {
            name: "Technician 1",
            live_latitude: 50.3,
            live_longitude: 4.65,
            live_location_last_update: "2026-01-04 12:00:00",
        },
        {
            name: "Technician 2",
            live_latitude: 50.26,
            live_longitude: 4.91,
            live_location_last_update: "2026-01-04 06:24:18",
        },
        {
            name: "Technician 3",
            live_latitude: 50.45,
            live_longitude: 4.36,
            live_location_last_update: "2026-01-04 11:00:00",
        },
    ]);
    pyEnv["planning.slot"].create([
        {
            name: "Intervention",
            partner_id: partner1,
            resource_ids: [resource1, resource2],
            start_datetime: "2026-01-04 15:00:00",
            end_datetime: "2026-01-04 16:00:00",
        },
        {
            name: "Collapsed Intervention",
            partner_id: partner2,
            resource_ids: [resource3],
            start_datetime: "2026-01-04 15:00:00",
            end_datetime: "2026-01-04 16:00:00",
        },
    ]);

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["partner_id"],
    });

    expect("div.o_map_view").toBeVisible({
        message: "The map should be visible",
    });
    expect("div.o_planning_field_service_live_map_view").toBeVisible({
        message: "The live map view should be visible",
    });

    expect("div.leaflet-marker-icon").toHaveCount(7);
    await contains(".o-map-renderer--pin-list-group-header:contains(Foo 2)").click();
    expect("div.leaflet-marker-icon").toHaveCount(5, {
        message: "The partner and user pins should not be visible",
    });
});

test.tags("mobile");
test("live map (mobile): captures user's live location, displays a pin for the user, and opens a popup when hovered", async () => {
    const pyEnv = await startServer();
    pyEnv["resource.resource"].write([1], {
        live_latitude: 50.26,
        live_longitude: 4.91,
        live_location_last_update: "2026-01-04 06:24:18",
    });

    await mountView({
        type: "map",
        resModel: "planning.slot",
    });
    expect("div.o_map_view").toBeVisible({
        message: "The map should be visible",
    });
    expect("div.o_planning_field_service_live_map_view").toBeVisible({
        message: "The live map view should be visible",
    });

    expect("div.leaflet-marker-icon").toHaveCount(3, {
        message:
            "There should be 3 markers on the map (current user location, one partner, one user)",
    });

    const userMarker = queryAll("div.leaflet-marker-icon:has(img)");
    expect(userMarker).toHaveCount(1, {
        message: "There should be one user marker on the map",
    });

    expect("div.leaflet-popup").toHaveCount(0, {
        message: "The user marker popup information should not be opened by default",
    });

    await contains(userMarker).click();
    await animationFrame();
    expect("div.leaflet-popup").toHaveCount(1, {
        message: "The user marker popup information should be opened when clicking the user marker",
    });

    const root = "div.leaflet-popup-content";
    expect(queryAll("img", { root })).toHaveCount(1, {
        message: "The user avatar should be visible on the popup",
    });
    expect(queryAllTexts("div.flex-column div", { root })).toEqual([
        "Mitchell Admin",
        "Rue du Blé, 17\n5556 Liège",
        "5 hours ago",
    ]);

    await contains(".leaflet-popup-close-button").click();
    await advanceTime(500);
    await waitForNone("div.leaflet-popup");
    expect("div.leaflet-popup").toHaveCount(0, {
        message: "The user marker popup information should be closed on exit",
    });
});

test.tags("desktop");
test("live map: user marker moves on refresh", async () => {
    const pyEnv = await startServer();
    pyEnv["resource.resource"].write([1], {
        live_latitude: 50.26,
        live_longitude: 4.91,
        live_location_last_update: "2026-01-04 06:24:18",
    });

    await mountWebClient();

    await getService("action").doAction({
        res_model: "planning.slot",
        type: "ir.actions.act_window",
        views: [[false, "map"]],
    });

    expect("div.o_map_view").toBeVisible({
        message: "The map should be visible",
    });
    expect("div.o_planning_field_service_live_map_view").toBeVisible({
        message: "The live map view should be visible",
    });

    let userMarker = queryFirst("div.leaflet-marker-icon:has(img)");
    expect(userMarker).toHaveCount(1, {
        message: "There should be one user marker on the map",
    });
    // initial position
    const markerPosition = userMarker._leaflet_pos;

    // update user live location
    pyEnv["resource.resource"].write([1], {
        live_latitude: 50.45,
        live_longitude: 4.36,
        live_location_last_update: "2026-01-04 12:00:00",
    });
    await getService("action").doAction("soft_reload");
    await animationFrame();
    userMarker = queryFirst("div.leaflet-marker-icon:has(img)");
    expect(userMarker._leaflet_pos.x).not.toBe(markerPosition.x);
    expect(userMarker._leaflet_pos.y).not.toBe(markerPosition.y);
});

test("live map: button redirection to focus on user pin", async () => {
    patchWithCleanup(Geolocation.prototype, {
        async _fetchAddressFromCoordinatesOSM() {
            return {
                street: "Sweat street",
                house_number: "17",
                city: "District",
                zip: "9999",
            };
        },
    });

    const pyEnv = await startServer();
    pyEnv["resource.resource"].write([1], {
        live_latitude: 40.0,
        live_longitude: 10.0,
        live_location_last_update: "2026-01-04 06:24:18",
    });

    const view = await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });
    const renderer = findComponent(view, (c) => c instanceof MapRenderer);

    expect(renderer.leafletMap.getCenter().lat).toBeCloseTo(50.1, { margin: 0.001 });
    expect(renderer.leafletMap.getCenter().lng).toBeCloseTo(4.775, { margin: 0.001 });

    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    await contains(".o-map-renderer--pin-list-group-header [data-icon='my_location']").click();
    // wait for the animation which takes a certain time...
    await advanceTime(2000);

    expect(renderer.leafletMap.getCenter().lat).toBeCloseTo(40.0, { margin: 0.001 });
    expect(renderer.leafletMap.getCenter().lng).toBeCloseTo(10.0, { margin: 0.001 });
});

test("live map: Google Map redirection starts from live user position", async () => {
    const pyEnv = await startServer();
    pyEnv["resource.resource"].write([1], {
        live_latitude: 50.26,
        live_longitude: 4.91,
        live_location_last_update: "2026-01-04 06:24:18",
    });

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });

    if (isSmall()) {
        await contains("button.o-control-panel-adaptive-dropdown").click();
        await contains(".o_bottom_sheet button.btn.btn-secondary").click();
    } else {
        await contains("button.btn.btn-secondary").click();
    }
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
    ]);

    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    await contains(".o-map-renderer--pin-list-group-header div button svg").click();
    expect.verifySteps(
        [
            "https://www.google.com/maps/dir/?api=1&origin=Rue%20du%20Bl%C3%A9%2C%2017%2C%205556%20Li%C3%A8ge&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
        ],
        { message: "The routing should start from the user live location" }
    );
});

test.tags("desktop");
test("live map: Google Map redirection starts from assigned resource's location", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    const pyEnv = await startServer();

    const employeeId = pyEnv["hr.employee"].create({ name: "René", resource_id: 1 });
    const resourceId = pyEnv["resource.resource"].create({
        name: "Material",
        assigned_employee_id: employeeId,
    });
    pyEnv["planning.slot"].create({
        name: "Test",
        resource_ids: [resourceId],
        start_datetime: "2026-01-04 08:00:00",
        end_datetime: "2026-01-04 15:00:00",
        partner_id: 520,
    });

    await mountView({
        type: "map",
        resModel: "planning.slot",
        groupBy: ["resource_ids"],
    });

    await contains(
        ".o-map-renderer--pin-list-group-header:contains(Material) div button svg"
    ).click();
    expect.verifySteps(
        [
            "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
        ],
        { message: "The routing should not have an origin" }
    );

    pyEnv["resource.resource"].write([1], {
        live_latitude: 50.26,
        live_longitude: 4.91,
        live_location_last_update: "2026-01-04 06:24:18",
    });

    // Trigger a reload of the model to reflect the located resource
    await contains(".o_searchview .o_searchview_icon").click();

    await contains(
        ".o-map-renderer--pin-list-group-header:contains(Material) div button svg"
    ).click();
    expect.verifySteps(
        [
            "https://www.google.com/maps/dir/?api=1&origin=Rue%20du%20Bl%C3%A9%2C%2017%2C%205556%20Li%C3%A8ge&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
        ],
        {
            message:
                "The routing should start from the material's assigned resource's live location",
        }
    );
});

test.tags("desktop");
test("live map: does not recompute routes when the current user's position changes", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    patchWithCleanup(PlanningFieldServiceLiveMapModel.prototype, {
        _fetchRoutes() {
            expect.step("_fetchRoutes");
            return {};
        },
    });

    await mountView({
        type: "map",
        resModel: "planning.slot",
    });

    expect.verifySteps(["_fetchRoutes"], {
        message: "The routes are computed when loading the view ",
    });

    await contains(".o_content [data-icon='my_location']").click();
    expect.verifySteps([], {
        message:
            "The routes should not be re-computed on user position change, as they start from the located resources' positions",
    });
});
