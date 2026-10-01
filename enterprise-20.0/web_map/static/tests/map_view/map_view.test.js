import {
    advanceTime,
    animationFrame,
    beforeEach,
    click,
    drag,
    expect,
    mockTimeZone,
    queryAllAttributes,
    queryAllTexts,
    queryFirst,
    queryOne,
    runAllTimers,
    test,
    waitFor,
} from "@odoo/hoot";
import {
    contains,
    defineModels,
    destroyApp,
    fields,
    findComponent,
    getService,
    isSmall,
    mockService,
    models,
    mountView,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
    toggleMenuItem,
    toggleMenuItemOption,
    toggleSearchBarMenu,
} from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { range } from "@web/core/utils/numbers";
import { session } from "@web/session";
import { WebClient } from "@web/webclient/webclient";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";
import { MapController } from "@web_map/map_view/map_controller";
import { MapModel } from "@web_map/map_view/map_model";
import { MapRenderer } from "@web_map/map_view/map_renderer";

const MAP_BOX_TOKEN = "token";

function getMapController(view) {
    return findComponent(view, (c) => c instanceof MapController);
}

function getMapRenderer(view) {
    return findComponent(view, (c) => c instanceof MapRenderer);
}

const TEST_RECORDS = {
    task: {
        oneRecord: [{ id: 1, name: "Foo", partner_id: 1 }],
        twoRecordsFieldDateTime: [
            { id: 1, name: "Foo", scheduled_date: false, partner_id: 1 },
            {
                id: 2,
                name: "Bar",
                scheduled_date: "2022-02-07 21:09:31",
                partner_id: 2,
            },
        ],
        twoRecords: [
            { id: 1, name: "FooProject", sequence: 1, partner_id: 1 },
            { id: 2, name: "BarProject", sequence: 2, partner_id: 2 },
        ],
        threeRecords: [
            {
                id: 1,
                name: "FooProject",
                sequence: 1,
                partner_id: 1,
                partner_ids: [1, 2],
            },
            {
                id: 2,
                name: "BarProject",
                sequence: 2,
                partner_id: 2,
                partner_ids: [1],
            },
            {
                id: 3,
                name: "FooBarProject",
                sequence: 3,
                partner_id: 1,
                partner_ids: [1],
            },
        ],
        fourPartners: [
            { id: 1, name: "Foo", partner_id: 1 },
            { id: 2, name: "Bar", partner_id: 2 },
            { id: 3, name: "Foo", partner_id: 3 },
            { id: 4, name: "Bar", partner_id: 4 },
        ],
        twoRecordOnePartner: [
            { id: 1, name: "FooProject", partner_id: 1 },
            { id: 2, name: "BarProject", partner_id: 1 },
        ],
        recordWithouthPartner: [{ id: 1, name: "Foo", partner_id: false }],
        anotherPartnerId: [{ id: 1, name: "FooProject", another_partner_id: 1 }],
    },
    partner: {
        coordinatesNoAddress: [
            {
                id: 1,
                name: "Foo",
                partner_latitude: 10.0,
                partner_longitude: 10.5,
            },
        ],
        oneLocatedRecord: [
            {
                id: 1,
                name: "Foo",
                partner_latitude: 10.0,
                partner_longitude: 10.5,
                contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                sequence: 1,
            },
        ],
        wrongCoordinatesNoAddress: [
            {
                id: 1,
                name: "Foo",
                partner_latitude: 10000.0,
                partner_longitude: 100000.5,
            },
        ],
        noCoordinatesGoodAddress: [
            {
                id: 1,
                name: "Foo",
                partner_latitude: 0,
                partner_longitude: 0,
                contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
            },
        ],
        twoRecordsAddressNoCoordinates: [
            {
                id: 2,
                name: "Foo",
                contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                sequence: 3,
            },
            {
                id: 1,
                name: "Bar",
                contact_address_complete: "Chaussée de Louvain 94, 5310 Éghezée",
                sequence: 1,
            },
        ],
        twoRecordsAddressCoordinates: [
            {
                id: 2,
                name: "Foo",
                partner_latitude: 10.0,
                partner_longitude: 10.5,
                contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                sequence: 3,
            },
            {
                id: 1,
                name: "Bar",
                partner_latitude: 10.0,
                partner_longitude: 10.5,
                contact_address_complete: "Chaussée de Louvain 94, 5310 Éghezée",
                sequence: 1,
            },
        ],
        twoRecordsOneUnlocated: [
            {
                id: 1,
                name: "Foo",
                contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                sequence: 3,
            },
            {
                id: 2,
                name: "Bar",
            },
        ],
        fourRecords: [
            {
                id: 1,
                name: "Foo",
                partner_latitude: 10.0,
                partner_longitude: 10.5,
                contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                sequence: 1,
                user_id: 1,
            },
            {
                id: 2,
                name: "Foo",
                partner_latitude: 11.0,
                partner_longitude: 11.5,
                contact_address_complete: "Chaussée de Wavre 50, 1367, Ramillies",
                sequence: 2,
                user_id: 2,
            },
            {
                id: 3,
                name: "Ba4",
                partner_latitude: 12.0,
                partner_longitude: 12.5,
                contact_address_complete: "Chaussée de Louvain 94, 5310 Éghezée",
                sequence: 3,
                user_id: false,
            },
            {
                id: 4,
                name: "Bar",
                partner_latitude: 12.5,
                partner_longitude: 13,
                contact_address_complete: "Rue du Laid Burniat 5, 1348 Ottignies-Louvain-la-Neuve",
                sequence: 4,
                user_id: false,
            },
        ],
        unlocatedRecords: [{ id: 1, name: "Foo" }],
        noCoordinatesWrongAddress: [
            {
                id: 1,
                name: "Foo",
                contact_address_complete: "Cfezfezfefes",
            },
        ],
    },
};

class Task extends models.Model {
    _name = "project.task";

    name = fields.Char();
    scheduled_date = fields.Datetime({ string: "Schedule date" });
    task_status = fields.Selection({
        string: "Status",
        selection: [
            ["abc", "ABC"],
            ["def", "DEF"],
            ["ghi", "GHI"],
        ],
    });
    sequence = fields.Integer();
    partner_id = fields.Many2one({
        string: "partner",
        relation: "res.partner",
    });
    another_partner_id = fields.Many2one({
        string: "another relation",
        relation: "res.partner",
    });
    partner_ids = fields.One2many({
        string: "Partners",
        comodel_name: "res.partner",
        relation: "res.partner",
        relation_field: "task_id",
    });

    _records = [{ id: 1, name: "project", partner_id: 1 }];
}

class Users extends models.Model {
    _name = "res.users";

    name = fields.Char();
    _records = [
        { id: 1, name: "Mitchell Admin" },
        { id: 2, name: "Marc Demo" },
    ];
}

class Partner extends models.Model {
    _name = "res.partner";

    name = fields.Char({ string: "Customer" });
    partner_latitude = fields.Float({ string: "Latitude" });
    partner_longitude = fields.Float({ string: "Longitude" });
    contact_address_complete = fields.Char({ string: "Address" });
    task_ids = fields.One2many({
        string: "Task",
        relation: "project.task",
        relation_field: "partner_id",
    });
    sequence = fields.Integer();
    user_id = fields.Many2one({
        string: "Salesperson",
        relation: "res.users",
    });

    _records = [
        {
            id: 1,
            name: "Foo",
            partner_latitude: 10.0,
            partner_longitude: 10.5,
            contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
            sequence: 1,
            user_id: 1,
        },
        {
            id: 2,
            name: "Foo",
            partner_latitude: 10.0,
            partner_longitude: 10.5,
            contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
            sequence: 3,
            user_id: 2,
        },
        {
            id: 3,
            name: "Bar",
            partner_latitude: 11.0,
            partner_longitude: 11.5,
            contact_address_complete: "Chaussée de Wavre 50, 1367, Ramillies",
            sequence: 4,
            user_id: false,
        },
    ];

    update_latitude_longitude() {
        return true;
    }
}

class Company extends models.Model {
    _name = "res.company";

    name = fields.Char();
    partner_id = fields.Many2one({ string: "Partner", relation: "res.partner" });

    _records = [];
}

defineModels([Task, Users, Partner, Company]);

const UNPATCHED_FETCH_COORDINATES_MB = Geolocation.prototype._fetchCoordinatesFromAddressMB;
const UNPATCHED_FETCH_ROUTE = Geolocation.prototype.fetchRoute;
const UNPATCHED_NOTIFY_COORDINATES = MapModel.prototype._notifyFetchedCoordinate;
beforeEach(() => {
    patchWithCleanup(Geolocation, {
        // set delay to 0 as _fetchCoordinatesFromAddressOSM is mocked
        OSM_COORDINATE_FETCH_DELAY: 0,
    });
    patchWithCleanup(Geolocation.prototype, {
        async _fetchCoordinatesFromAddressMB(query) {
            const failResponse = [];
            switch (query) {
                case "Cfezfezfefes":
                    return failResponse;
                case "":
                    return failResponse;
            }
            const coordinates = { latitude: 10.5, longitude: 10.0 };
            return [coordinates];
        },
        async _fetchCoordinatesFromAddressOSM(query) {
            const coordinates = [];
            coordinates[0] = { latitude: 10.0, longitude: 10.5 };
            switch (query) {
                case "Cfezfezfefes":
                    return [];
                case "":
                    return [];
            }
            return coordinates;
        },
        async fetchRoute(coords, routing) {
            const legs = [];
            for (let i = 1; i < coords.length; i++) {
                const coordinates = [];
                coordinates[0] = [10, 10.5];
                coordinates[1] = [10, 10.6];
                const geometry = { coordinates };
                const steps = [];
                steps[0] = { geometry };
                legs.push({ steps: steps });
            }
            if (legs.length == 0) {
                return null;
            }
            return { legs, duration: 3000, distance: 10000 };
        },
    });
    patchWithCleanup(MapModel.prototype, {
        _notifyFetchedCoordinate(data) {
            // do not notify in tests as coords fetching is " synchronous "
        },
    });
    patchWithCleanup(browser, {
        open(url) {
            expect.step(url);
        },
    });
});

//--------------------------------------------------------------------------
// Testing data fetching
//--------------------------------------------------------------------------

/**
 * data: no record
 * Should have no record
 * Should have no marker
 * Should have no route
 */
test("Create a view with no record", async () => {
    expect.assertions(6);
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    Task._records = [];
    onRpc("project.task", "web_search_read", ({ kwargs }) => {
        const specification = kwargs.specification;
        expect(specification.partner_id).toEqual({
            fields: {
                contact_address_complete: {},
                display_name: {},
                partner_latitude: {},
                partner_longitude: {},
            },
        });
        expect(specification.name).toEqual({});
    });
    onRpc("res.partner", "search_read", () => {
        throw new Error("Should not search_read the partners if there are no partner");
    });
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `
                    <map res_partner="partner_id" routing="optimized">
                        <field name="name" string="Project"/>
                        <field name="partner_ids" string="Project"/>
                    </map>
                `,
    });
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "No marker should be on a the map.",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );

    await click("button.btn.btn-secondary");
    expect.verifySteps(["https://www.google.com/maps/dir/?api=1"]);
});

/**
 * data: one record that has no partner linked to it
 * The record shouldn't be kept and displayed in the list of records
 * should have no marker
 * Should have no route
 */
test("Create a view with one record that has no partner", async () => {
    Task._records = TEST_RECORDS.task.recordWithouthPartner;
    Partner._records = [];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "No marker should be on a the map.",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
    await contains(".o-map-renderer--pin-list-group-header:contains(Unlocated)").click();
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
});

/**
 * data: one record that has a partner which has coordinates but no address
 * One record
 * One marker
 * no route
 */
test("Create a view with one record and a partner located by coordinates", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.coordinatesNoAddress;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be one marker on the map",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
});

/**
 * data: one record linked to one partner with no address and wrong coordinates
 * api: MapBox
 * record shouldn't be kept and displayed in the list
 * no route
 * no marker
 */
test("Create view with one record linked to a partner with wrong coordinates with MB", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.wrongCoordinatesNoAddress;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "There should be no marker on the map",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
});

/**
 * data: one record linked to one partner with no address and wrong coordinates
 * api: OpenStreet Map
 * record should be kept
 * no route
 * no marker
 */
test("Create view with one record linked to a partner with wrong coordinates with OSM", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.wrongCoordinatesNoAddress;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "There should be no marker on the map",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
});
/**
 * data: one record linked to one partner with no coordinates and good address
 * api: OpenStreet Map
 * caching RPC called, assert good args
 * one record
 * no route
 */
test("Create View with one record linked to a partner with no coordinates and right address OSM", async () => {
    expect.assertions(5);

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.noCoordinatesGoodAddress;

    onRpc("res.partner", "update_latitude_longitude", ({ args }) => {
        expect(args[0]).toHaveLength(1, {
            message: "There should be one record needing caching",
        });
        expect(args[0][0].id).toBe(1, { message: "The records's id should be 1" });
        return {};
    });
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be one marker on the map",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: 2 records linked to different partners
 * api: OpenStreet Map
 * caching RPC called, assert good args
 * one record
 * no route
 */
test("Create View with two records linked to different partners with no coordinates and right address OSM (with fetch delay)", async () => {
    expect.assertions(9);

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    patchWithCleanup(Geolocation, {
        OSM_COORDINATE_FETCH_DELAY: 1000,
    });
    patchWithCleanup(MapModel.prototype, {
        _notifyFetchedCoordinate: UNPATCHED_NOTIFY_COORDINATES,
    });

    onRpc("res.partner", "update_latitude_longitude", ({ args }) => {
        expect(args[0]).toHaveLength(2, {
            message: "There should be two records needing caching",
        });
        expect(args[0].map((r) => r.id)).toEqual([1, 2], {
            message: "The records's ids should be 1 and 2",
        });
        return {};
    });
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect("div.o-map-renderer--alert:contains(Locating new addresses...)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    await runAllTimers();
    await waitFor("div.leaflet-marker-icon text");
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(0);
    expect("div.o-map-renderer--alert:contains(Locating new addresses...)").toHaveCount(0);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        2
    );
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: one record linked to one partner with no coordinates and good address
 * api: MapBox
 * caching RPC called, assert good args
 * one record
 * no route
 */
test("Create View with one record linked to a partner with no coordinates and right address MB", async () => {
    expect.assertions(5);

    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.noCoordinatesGoodAddress;
    onRpc("res.partner", "update_latitude_longitude", ({ args }) => {
        expect(args[0]).toHaveLength(1, {
            message: "There should be one record needing caching",
        });
        expect(args[0][0].id).toBe(1, { message: "The records's id should be 1" });
        return {};
    });

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be one marker on the map",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: one record linked to a partner with no coordinates and no address
 * api: MapBox
 * 1 record
 * no route
 * no marker
 */
test("Create view with no located record", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.unlocatedRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "No marker should be on a the map.",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: one record linked to a partner with no coordinates and no address
 * api: OSM
 * one record
 * no route
 * no marker
 */
test("Create view with no located record OSM", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.unlocatedRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "No marker should be on a the map.",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: one record linked to a partner with no coordinates and wrong address
 * api: OSM
 * one record
 * no route
 * no marker
 */
test("Create view with no badly located record OSM", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.noCoordinatesWrongAddress;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "No marker should be on a the map.",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: one record linked to a partner with no coordinates and wrong address
 * api: mapbox
 * one record
 * no route
 * no marker
 */

test("Create view with no badly located record MB", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.noCoordinatesWrongAddress;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header:contains(Unlocated)").toHaveCount(1);
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        0
    );
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "No marker should be on a the map.",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * data: 2 records linked to the same partner
 * 2 records
 * 2 markers
 * no route
 * same partner object
 * 1 caching request
 */
test("Create a view with two located records same partner", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecordOnePartner;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        2
    );
    expect("div.o_map_marker_content svg text").toHaveText("2", {
        message: "There should be a marker for two records",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1);
});

/**
 * data: 2 records linked to differnet partners
 * 2 records
 * 2 markers
 * no route
 * different partner object.
 * 2 caching
 */
test("Create a view with two located records different partner", async () => {
    expect.assertions(5);
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;
    onRpc("res.partner", "update_latitude_longitude", ({ args }) => {
        expect(args[0]).toHaveLength(2, {
            message: "Should have 2 record needing caching",
        });
        return {};
    });

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect("li.cursor-pointer.o-map-renderer--pin-clickable").toHaveCount(2, {
        message: "There should be 2 located records",
    });
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1);
    expect(controller.model.data.records[0].partner).not.toBe(
        controller.model.data.records[1].partner,
        { message: "The records should have the same partner object as a property" }
    );
});

/**
 * data: 2 valid res.partner records
 * test the case where the model is res.partner and the "res.partner" field is the id
 * should have 2 records,
 * 2 markers
 * no route
 */
test("Create a view with res.partner", async () => {
    expect.assertions(4);
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Partner._records = [
        {
            id: 2,
            name: "Foo",
            contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
            sequence: 3,
        },
        {
            id: 1,
            name: "FooBar",
            contact_address_complete: "Chaussée de Louvain 94, 5310 Éghezée",
            sequence: 1,
        },
    ];
    onRpc("res.partner", "web_search_read", ({ kwargs }) => {
        expect(kwargs.specification).toEqual({
            contact_address_complete: {},
            display_name: {},
            id: {},
            partner_latitude: {},
            partner_longitude: {},
        });
    });
    await mountView({
        type: "map",
        resModel: "res.partner",
        arch: `<map res_partner="id" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        2
    );
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
});

/**
 * Data: 3 partner records with user_id used as groupBy
 * Test if the map view displays the many2one field's name as the group name
 */
test("Create a view with many2one groupBy and res.partner model", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "res.partner",
        arch: `<map res_partner="id" />`,
        groupBy: ["user_id"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(3, {
        message: "Should have 3 groups",
    });

    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(
        ["Mitchell Admin", "Marc Demo", "None"],
        {
            message: "Should have correct group headers",
        }
    );

    expect(".o-map-renderer--pin-list-details").toHaveCount(3, {
        message: "Should have 3 group detail sections",
    });

    expect(".o-map-renderer--pin-list-details li").toHaveCount(4, {
        message: "Should have 4 total records across all groups",
    });
});

/**
 * data: 2 records linked to differnet partners
 * 2 records
 * 1 route
 * different partner object.
 * 2 caching
 */
test("Create a view with two located records different partner with groupBy (OSM with fetch delay)", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    patchWithCleanup(Geolocation, {
        OSM_COORDINATE_FETCH_DELAY: 1000,
    });
    patchWithCleanup(MapModel.prototype, {
        _notifyFetchedCoordinate: UNPATCHED_NOTIFY_COORDINATES,
    });

    await mountView({
        type: "map",
        resModel: "res.partner",
        arch: `<map res_partner="id" />`,
        groupBy: ["user_id"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["None", "Unlocated"], {
        message: "Only one record located",
    });
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    expect("div.o-map-renderer--alert:contains(Locating new addresses...)").toHaveCount(1);
    await runAllTimers();
    await waitFor("div.leaflet-marker-icon text");
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["None"], {
        message: "All records located",
    });
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        2
    );
    expect("div.o-map-renderer--alert:contains(Locating new addresses...)").toHaveCount(0);
});

/**
 * data: 3 records linked to one located partner and one unlocated
 * test if only the 2 located records are displayed
 */
test("Create a view with 2 located records and 1 unlocated", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.threeRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsOneUnlocated;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.data.records.length).toBe(3);
    expect(controller.model.data.records[0].partner.id).toBe(1, {
        message: "The partner's id should be 1",
    });
    expect(controller.model.data.records[1].partner.id).toBe(2, {
        message: "The partner's id should be 2",
    });
    expect(controller.model.data.records[2].partner.id).toBe(1, {
        message: "The partner's id should be 1",
    });
});

test.tags("desktop");
test("Change load limit", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.threeRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" limit="2" />`,
    });
    expect(`.o_pager_counter .o_pager_value`).toHaveText("1-2");
    expect(`.o_pager_counter span.o_pager_limit`).toHaveText("3");
});

test.tags("desktop");
test("Load limit set at the action level is applied", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.threeRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
        limit: 2,
    });
    expect(`.o_pager_counter .o_pager_value`).toHaveText("1-2");
    expect(`.o_pager_counter span.o_pager_limit`).toHaveText("3");
});

//--------------------------------------------------------------------------
// Renderer testing
//--------------------------------------------------------------------------

test("Google Maps redirection", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"></map>`,
    });

    await click("button.btn.btn-secondary");
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&waypoints=Chauss%C3%A9e%20de%20Louvain%2094%2C%205310%20%C3%89ghez%C3%A9e|Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
    ]);
    await contains(".leaflet-marker-icon").click();
    expect("div.o_map_popover a.btn.btn-primary").toHaveAttribute(
        "href",
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
        { message: "The URL of the link should contain the address" }
    );
});

test("Google Maps redirection (with routing = true)", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized"></map>`,
    });

    await click("button.btn.btn-secondary");
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies&waypoints=Chauss%C3%A9e%20de%20Louvain%2094%2C%205310%20%C3%89ghez%C3%A9e",
    ]);

    await contains(".leaflet-marker-icon").click();
    expect("div.o_map_popover a.btn.btn-primary").toHaveAttribute(
        "href",
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
        { message: "The URL of the link should contain the address" }
    );
});

test("Google Maps redirection with grouping", async () => {
    Task._records = TEST_RECORDS.task.fourPartners;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized"></map>`,
        groupBy: ["name"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    // Test the controller level Google maps button
    await click(".o_control_panel button.btn.btn-secondary");
    await contains(".o-map-renderer--pin-list-container [data-icon='arrow_drop_down']").click(); // Fold first group
    await click(".o_control_panel button.btn.btn-secondary");
    await contains(".o-map-renderer--pin-list-container [data-icon='arrow_drop_down']").click(); // Fold second and last group
    await click(".o_control_panel button.btn.btn-secondary");
    // Test the group level google maps button
    await contains(".o-map-renderer--pin-list-group-header div button").click();
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&destination=Rue%20du%20Laid%20Burniat%205%2C%201348%20Ottignies-Louvain-la-Neuve&waypoints=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies|Chauss%C3%A9e%20de%20Louvain%2094%2C%205310%20%C3%89ghez%C3%A9e|Chauss%C3%A9e%20de%20Wavre%2050%2C%201367%2C%20Ramillies",
        "https://www.google.com/maps/dir/?api=1&destination=Rue%20du%20Laid%20Burniat%205%2C%201348%20Ottignies-Louvain-la-Neuve&waypoints=Chauss%C3%A9e%20de%20Wavre%2050%2C%201367%2C%20Ramillies",
        "https://www.google.com/maps/dir/?api=1",
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Louvain%2094%2C%205310%20%C3%89ghez%C3%A9e&waypoints=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
    ]);
});

test("Unicity of coordinates in Google Maps url", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecordOnePartner;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });
    await click("button.btn.btn-secondary");
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&waypoints=Chauss%C3%A9e%20de%20Louvain%2094%2C%205310%20%C3%89ghez%C3%A9e",
    ]);
    await contains(".leaflet-marker-icon").click();
    expect("div.o_map_popover a.btn.btn-primary").toHaveAttribute(
        "href",
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Louvain%2094%2C%205310%20%C3%89ghez%C3%A9e",
        { message: "The URL of the link should contain the address" }
    );
});

test("test the position of pin", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    expect(".o_map_marker").toHaveCount(1, {
        message: "Should have one marker created",
    });
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
    const renderer = getMapRenderer(view);
    expect(renderer.markers[0].getLatLng().lat).toBe(10, {
        message: "The latitude should be the same as the record",
    });
    expect(renderer.markers[0].getLatLng().lng).toBe(10.5, {
        message: "The longitude should be the same as the record",
    });
});

test("Map without records centers itself on active company", async () => {
    Partner._records = [
        { id: 1, name: "Foo", partner_latitude: 35.23, partner_longitude: 45.52 },
        { id: 2, name: "Bar", partner_latitude: 31.1, partner_longitude: 40.5 },
    ];
    Task._records = [];
    Company._records = [
        { id: 1, name: "active_company ", partner_id: 1 }, // By default user.activeCompany.id is 1
        { id: 2, name: "some_other_company", partner_id: 2 },
    ];
    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `
                    <map res_partner="partner_id" routing="optimized">
                    </map>
                `,
    });
    const renderer = getMapRenderer(view);
    expect(renderer.leafletMap.getCenter().lat).toBeCloseTo(35.23, { margin: 0.0001 });
    expect(renderer.leafletMap.getCenter().lng).toBeCloseTo(45.52, { margin: 0.0001 });
});

/**
 * data: two located records
 * Create an empty map
 */
test("Create of a empty map", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "res.partner",
        arch: `<map />`,
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.resPartnerField).toBe(null, {
        message: "the resPartnerField should not be set",
    });

    expect(".o_map_view").toHaveClass("o_view_controller");
    expect(".leaflet-map-pane").toHaveCount(1, {
        message: "If the map exists this div should exist",
    });
    expect(".leaflet-pane .leaflet-tile-pane > *").toHaveCount(1, {
        message: "The map tiles should have been happened to the DOM",
    });
    // if element o-map-renderer--container has class leaflet-container then
    // the map is mounted
    expect(".o-map-renderer--container").toHaveClass("leaflet-container", {
        message: "the map should be in the DOM",
    });

    expect(".leaflet-overlay-pane > *").toHaveCount(0, {
        message: "Should have no showing route",
    });
});

/**
 * two located records
 * without routing or default_order
 * normal marker icon
 * test the click on them
 */

test("Create view with normal marker icons", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.routing).toBe(false, {
        message: "The routing option should not be enabled",
    });

    expect(".leaflet-marker-icon").toHaveCount(1, { message: "There should be 1 marker" });
    expect(".leaflet-overlay-pane path").toHaveCount(0);

    await contains(".leaflet-marker-icon").click();

    expect(".o_map_popover").toHaveCount(1, {
        message: "Should have one showing popup",
    });

    await contains("div.leaflet-container").click();
    // wait for the popup's destruction which takes a certain time...
    for (let i = 0; i < 15; i++) {
        await animationFrame();
    }

    expect(".o_map_popover").toHaveCount(0, {
        message: "Should not have any showing popup",
    });
});

/**
 * two located records
 * with default_order
 * no numbered icon
 * test click on them
 * asserts that the rpc receive the right parameters
 */

test("Create a view with default_order", async () => {
    expect.assertions(6);

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;
    onRpc("project.task", "web_search_read", ({ kwargs }) => {
        expect(kwargs.order).toBe("name ASC", {
            message: "The sorting order should be on the field name in a ascendant way",
        });
    });

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" default_order="name" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.routing).toBe(false, {
        message: "The routing option should not be enabled",
    });
    expect("div.leaflet-marker-icon").toHaveCount(1, { message: "There should be 1 marker" });
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
    expect(".o_map_popover").toHaveCount(0, {
        message: "Should have no showing popup",
    });
    await contains("div.leaflet-marker-icon").click();
    expect(".o_map_popover").toHaveCount(1, {
        message: "Should have one showing popup",
    });
});

/**
 * two locted records
 * with routing enabled
 * numbered icon
 * test click on route
 */

test("Create a view with routing and routing ui", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.routing).toBe("optimized", {
        message: "The routing option should be enabled",
    });

    const renderer = getMapRenderer(view);
    expect(renderer.polylines.length).toBe(1, {
        message: "Should have 1 computed route group",
    });
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
    await expect("path[stroke='#007E82']").toHaveAttribute("stroke-opacity", "0.5", {
        message: "The opacity of the polyline should be 0.5",
    });
    expect(".leaflet-tooltip-pane .leaflet-tooltip").toHaveText("10 km in 50m", {
        message: "A leaflet tooltip should appear",
    });
});

test("Create a view with grouped routing", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route, params) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    trips: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [10, 10],
                                                    [11, 11],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 2000,
                        },
                    ],
                }); // test returning something that looks like the actual api
            }
        },
    });

    Task._records = TEST_RECORDS.task.fourPartners;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
        groupBy: ["name"],
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.routing).toBe("optimized", {
        message: "The routing option should be enabled",
    });

    expect.verifySteps([
        "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/10.5,10;12.5,12?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
        "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/11.5,11;13,12.5?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
    ]);

    const renderer = getMapRenderer(view);
    expect(renderer.polylines.length).toBe(2, {
        message: "Should have 2 computed route group",
    });
});

/**
 * routing with token and one located record
 * No route
 */
test("create a view with routing and one located record", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.routing).toBe("optimized", {
        message: "The routing option should be enabled",
    });
    const renderer = getMapRenderer(view);
    expect(renderer.polylines.length).toBe(0, {
        message: "Should have no computed route",
    });
});

/**
 * no mapbox token
 * assert that the view uses the right api and routes
 */
test("CreateView with empty mapbox token setting", async () => {
    Task._records = TEST_RECORDS.task.recordWithouthPartner;
    Partner._records = [];

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.geolocation.mapBoxToken).toBe("", {
        message: "The token should be an empty string",
    });
    expect(controller.model.geolocation.useMapBoxAPI).toBe(false, {
        message: "model should not use mapbox",
    });
});

/**
 * wrong mapbox token
 * assert that the view uses the openstreetmap api
 */
test("Create a view with wrong map box setting", async () => {
    patchWithCleanup(session, { map_box_token: "vrve" });

    patchWithCleanup(Geolocation.prototype, {
        _fetchCoordinatesFromAddressMB: UNPATCHED_FETCH_COORDINATES_MB,
    });

    mockService("http", {
        get: (route) => {
            if (route.includes("api.mapbox.com")) {
                if (this.mapBoxToken !== MAP_BOX_TOKEN) {
                    return Promise.reject({ status: 401 });
                }
                return Promise.resolve();
            }
        },
    });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.geolocation.mapBoxToken).toBe("vrve", {
        message: "The token should be kept",
    });
    expect(controller.model.geolocation.useMapBoxAPI).toBe(false, {
        message: "model should not use mapbox",
    });
});

/**
 * wrong mapbox token fails at catch at route computing
 */
test("create a view with wrong map box setting and located records", async () => {
    patchWithCleanup(session, { map_box_token: "frezfre" });

    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route) => {
            if (route.includes("api.mapbox.com")) {
                if (this.mapBoxToken !== MAP_BOX_TOKEN) {
                    return Promise.reject({ status: 401 });
                }
                return Promise.resolve();
            }
        },
    });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.geolocation.mapBoxToken).toBe("frezfre", {
        message: "The token should be kept",
    });
    expect(controller.model.geolocation.useMapBoxAPI).toBe(false, {
        message: "model should not use mapbox",
    });
});

/**
 * create view with right map box token
 * assert that the view uses the map box api
 */
test("Create a view with the right map box token", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.recordWithouthPartner;
    Partner._records = [];

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.geolocation.mapBoxToken).toBe("token", {
        message: "The token should be the right token",
    });
    expect(controller.model.geolocation.useMapBoxAPI).toBe(true, {
        message: "model should not use mapbox",
    });
});

/**
 * data: two located records
 */

test("Click on pin shows popup, click on another shuts the first and open the other", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect(".leaflet-pane .leaflet-popup-pane > *").toHaveCount(0, {
        message: "The popup div should be empty",
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_map_popover").toHaveCount(1, {
        message: "The popup div should contain one element",
    });

    // the element isn't visible
    await contains(".leaflet-map-pane", { visible: false }).click();
    await animationFrame();
    // wait for the popup's destruction which takes a certain time...
    for (let i = 0; i < 15; i++) {
        await animationFrame();
    }
    expect(".leaflet-pane .leaflet-popup-pane > *").toHaveCount(0, {
        message: "The popup div should be empty",
    });
});

/**
 * data: two located records
 * asserts that all the records are shown on the map
 */
test("assert that all the records are shown on the map", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    const mapX = queryOne(".leaflet-map-pane")._leaflet_pos.x;
    const mapY = queryOne(".leaflet-map-pane")._leaflet_pos.y;
    expect(mapX - queryOne("div.leaflet-marker-icon")._leaflet_pos.x).toBeLessThan(0, {
        message:
            "If the marker is currently shown on the map, the subtraction of latitude should be under 0",
    });
    expect(mapY - queryOne("div.leaflet-marker-icon")._leaflet_pos.y).toBeLessThan(0);
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
});

/**
 * data: two located records
 * asserts that the right fields are shown in the popup
 */
test("Content of the marker popup with one field", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `
                <map res_partner="partner_id" routing="optimized" hide_name="1" hide_address="1">
                    <field name="name" string="Name" />
                </map>
            `,
    });
    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > *").toHaveCount(2, {
        message: "The popup should have two elements for one field",
    });
    expect(queryAllTexts(".o_map_card_grid > *")).toEqual(["Name", "Foo"], {
        message: "Field row's text should be 'Name Foo'",
    });
    expect(".o_popover_footer > *").toHaveCount(2, {
        message: "The popup should contain 2 buttons",
    });
});

/**
 * data: two located records
 * asserts that the right fields are shown in the popup
 */
test("Content of the marker popup with one record without address", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.coordinatesNoAddress;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: ` <map res_partner="partner_id" hide_name="1"> </map> `,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_map_card_grid > *").toHaveCount(2, {
        message: "The popup should have two elements for one field",
    });
    expect(queryAllTexts(".o_map_card_grid > *")).toEqual(["Geolocation", "10, 10.5"], {
        message: "Field row's text should be 'Geolocation  10, 10.5'",
    });
});

test("Content of the marker popup with date time", async () => {
    mockTimeZone(+2); // UTC+2
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecordsFieldDateTime;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates.map((r) => ({ ...r }));
    Partner._records[0].partner_latitude = 11.0;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="true" hide_name="true" hide_address="true">
                    <field name="scheduled_date" string="Date"/>
                </map>`,
    });

    await contains("div.leaflet-marker-icon:first-child").click();

    expect(".o_map_card_grid > *").toHaveCount(0, {
        message: "It should not contains a value node because it's not scheduled",
    });

    await contains("div.leaflet-marker-icon:last-child").click();

    expect(".o_map_card_grid > div:nth-child(2)").toHaveText("Feb 7, 2022, 11:09 PM", {
        message: 'The time  "2022-02-07 21:09:31" should be in the local timezone',
    });
});

/**
 * data: two located records
 * asserts that no field is shown in popup
 */

test("Content of the marker with no field", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressNoCoordinates;
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" hide_name="1" hide_address="1" />`,
    });
    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > *").toHaveCount(0, {
        message: "The popup should have only the button",
    });
    expect(".o_popover_footer > *").toHaveCount(2, {
        message: "The popup should contain 2 buttons",
    });
});

test("Attribute: hide_name", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" hide_name="1" />`,
    });

    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > *").toHaveCount(2, {
        message: "The popup should have two elements for one field",
    });
    expect(".o_map_card_grid > div:nth-child(1)").toHaveText("Address", {
        message: "The popup should have address field",
    });
});

test("Render partner address field in popup", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" hide_name="1" />`,
    });

    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > *").toHaveCount(2, {
        message: "The popup should have two elements from one field",
    });
    expect(".o_map_card_grid > div:nth-child(1)").toHaveText("Address", {
        message: "The popup should have address field",
    });
    expect(".o_map_card_grid > div:nth-child(2)").toHaveText(
        "Chaussée de Namur 40, 1367, Ramillies",
        {
            message: "The popup should have correct address",
        }
    );
});

test("Hide partner address field in popup", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" hide_address="1" />`,
    });

    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > *").toHaveCount(0, { message: "The popup should have 0 field" });
    expect(".o_popover_header").toHaveText("Foo", {
        message: "The popup header should have correct name",
    });
});

test("Handle records of same co-ordinates in marker", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be a one marker",
    });
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });

    await contains("div.leaflet-marker-icon").click();

    expect(".o_map_card_grid > *").toHaveCount(2, {
        message: "The popup should have two elements for one field",
    });
    expect(".o_map_card_grid > div:nth-child(1)").toHaveText("Address", {
        message: "The popup should have address field",
    });
});

test("popover shows View, not Edit, when the marker groups several records", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_footer button.o_open_record_btn").toHaveText("View", {
        message: "opening several records leads to a list view, not a form view",
    });
});

test("popover: old-style top-level fields definition", async () => {
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id">
                <field name="name" string="Project"/>
            </map>`,
    });
    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_header").toHaveText("project");
    expect(queryAllTexts(".o_popover_body .o_map_card_grid > *")).toEqual([
        "Address",
        "Chaussée de Namur 40, 1367, Ramillies",
        "Project",
        "project",
    ]);
    expect(".o_popover_footer button.o_open_record_btn").toHaveText("Edit");
    expect(".o_popover_footer a.btn-primary").toHaveText("Navigate to");
});

test("popover node with default body and footer", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id">
                <popover>
                    <templates>
                    </templates>
                </popover>
            </map>
        `,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_header").toHaveText("Foo", {
        message: "The default header should render the record name",
    });
    expect(".o_popover_body .o_map_card_grid > *").toHaveCount(2, {
        message: "The default body should render the address",
    });
    expect(".o_popover_body .o_map_card_grid > div:nth-child(1)").toHaveText("Address");
    expect(".o_popover_footer button.o_open_record_btn").toHaveText("Edit");
    expect(".o_popover_footer a.btn-primary").toHaveText("Navigate to");
});

test('popover is readonly when edit="0" on the arch', async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" edit="0" />`,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_footer button.o_open_record_btn").toHaveText("View");
});

test("priority field can be edited in the popover when the arch allows it", async () => {
    Task._fields.priority = fields.Selection({
        selection: [
            ["0", "Low"],
            ["1", "High"],
        ],
    });
    Task._records = [{ id: 1, name: "Foo", partner_id: 1, priority: "0" }];
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    onRpc("web_save", ({ args }) => expect.step(`web_save: ${JSON.stringify(args[1])}`));

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id">
                <popover>
                    <templates>
                        <t t-name="popover-body">
                            <field name="priority" widget="priority"/>
                        </t>
                    </templates>
                </popover>
            </map>
        `,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_map_popover .o_priority_star").toHaveCount(1, {
        message: "the priority field should be rendered as a clickable widget",
    });
    await contains(".o_map_popover button.o_priority_star").click();
    expect.verifySteps([`web_save: {"priority":"1"}`]);
});

test('priority field cannot be edited in the popover when edit="0" on the arch', async () => {
    Task._fields.priority = fields.Selection({
        selection: [
            ["0", "Low"],
            ["1", "High"],
        ],
    });
    Task._records = [{ id: 1, name: "Foo", partner_id: 1, priority: "0" }];
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id" edit="0">
                <popover>
                    <templates>
                        <t t-name="popover-body">
                            <field name="priority" widget="priority"/>
                        </t>
                    </templates>
                </popover>
            </map>
        `,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_map_popover button.o_priority_star").toHaveCount(0, {
        message: "the priority field should be rendered as a non-interactive widget",
    });
    expect(".o_map_popover span.o_priority_star").toHaveCount(1);
});

test("popover node with card_id attribute", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    Task._views = {
        "card,1": /* xml */ `
            <card>
                <templates>
                    <t t-name="card">
                        <div class="o_custom_card_body">
                            <field name="name"/>
                        </div>
                    </t>
                </templates>
            </card>
        `,
    };

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `
            <map res_partner="partner_id">
                <popover card_id="1"/>
            </map>
        `,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_header").toHaveCount(0);
    expect(".o_popover_body .o_custom_card_body").toHaveCount(1);
    expect(".o_popover_body").toHaveText("Foo");
});

test.tags("desktop");
test("Pager", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = range(1, 102).map((index) => ({
        id: index,
        name: "project",
        partner_id: index,
    }));
    Partner._records = range(1, 102).map((index) => ({
        id: index,
        name: "Foo",
        partner_latitude: 10.0,
        partner_longitude: 10.5,
    }));

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });
    expect(".o_pager").toHaveCount(1);
    expect(`.o_pager_counter .o_pager_value`).toHaveText("1-80", {
        message: "current pager value should be 1-20",
    });
    expect(`.o_pager_counter span.o_pager_limit`).toHaveText("101", {
        message: "current pager limit should be 21",
    });

    await contains(`.o_pager button.o_pager_next`).click();

    expect(`.o_pager_counter .o_pager_value`).toHaveText("81-101", {
        message: "pager value should be 21-40",
    });
});

test("New domain", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = [
        { id: 1, name: "FooProject", sequence: 1, partner_id: 1 },
        { id: 2, name: "BarProject", sequence: 2, partner_id: 2 },
    ];
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
        searchViewArch: `
                <search>
                    <filter name="f_1" string="Filter 1" domain="[('name', '=', 'FooProject')]"/>
                    <filter name="f_2" string="Filter 2" domain="[('name', '=', 'Foofezfezf')]"/>
                    <filter name="f_3" string="Filter 3" domain="[('name', 'like', 'Project')]"/>
                </search>
            `,
    });
    const controller = getMapController(view);
    expect(controller.model.data.records).toHaveLength(2, {
        message: "There should be 2 records",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1);
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });

    await toggleSearchBarMenu();
    await toggleMenuItem("Filter 1");

    expect(controller.model.data.records).toHaveLength(1, {
        message: "There should be 1 record",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be 1 marker on the map",
    });

    await toggleMenuItem("Filter 1");
    await toggleMenuItem("Filter 2");

    expect(controller.model.data.records).toHaveLength(0, {
        message: "There should be no record",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    expect("div.leaflet-marker-icon").toHaveCount(0, {
        message: "There should be 0 marker on the map",
    });

    await toggleMenuItem("Filter 2");
    await toggleMenuItem("Filter 3");

    expect(controller.model.data.records).toHaveLength(2, {
        message: "There should be 2 record",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1);
    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be 1 marker on the map",
    });
    expect("div.leaflet-marker-icon .o-map-renderer-number").toHaveText("2", {
        message: "There should be a marker for two records",
    });
});

test("Toggle grouped pin lists", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.threeRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
        groupBy: ["partner_id"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(2, {
        message: "Should have 2 groups",
    });
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["Bar", "Foo"]);
    expect(".o-map-renderer--pin-list-details").toHaveCount(2);
    expect(".o-map-renderer--pin-list-details li").toHaveCount(3);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject\nFooBarProject",
        "BarProject",
    ]);

    await contains(".o-map-renderer--pin-list-group-header:eq(1)").click();

    expect(".o-map-renderer--pin-list-group-header").toHaveCount(2, {
        message: "Should still have 2 groups",
    });
    expect(".o-map-renderer--pin-list-details").toHaveCount(1);
    expect(".o-map-renderer--pin-list-details li").toHaveCount(2);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject\nFooBarProject",
    ]);

    await contains(".o-map-renderer--pin-list-group-header:eq(0)").click();

    expect(".o-map-renderer--pin-list-details").toHaveCount(0);

    await contains(".o-map-renderer--pin-list-group-header:eq(1)").click();

    expect(".o-map-renderer--pin-list-details").toHaveCount(1);
    expect(".o-map-renderer--pin-list-details li").toHaveCount(1);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual(["BarProject"]);
});

test("Toggle grouped one2many pin lists", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.threeRecords.map((r) => ({ ...r }));
    Task._records[1].partner_ids = [1, 3];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"/>`,
        groupBy: ["partner_ids"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(3, {
        message: "Should have 3 groups",
    });

    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["Foo", "Foo", "Bar"]);

    expect(".o-map-renderer--pin-list-details").toHaveCount(3);
    expect(".o-map-renderer--pin-list-details li").toHaveCount(5);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject\nBarProject\nFooBarProject",
        "FooProject",
        "BarProject",
    ]);
    expect(".leaflet-marker-icon").toHaveCount(3);
});

test("Check groupBy on datetime field", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._fields["scheduled_date"] = fields.Datetime({
        string: "Schedule date",
    });
    Task._records = [
        { id: 1, name: "FooProject", sequence: 1, partner_id: 1, scheduled_date: false },
    ];
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
        searchViewId: false,
        searchViewArch: `
                <search>
                    <group expand='0' string='Group By'>
                        <filter string="scheduled_date" name="scheduled_date" context="{'group_by': 'scheduled_date'}"/>
                    </group>
                </search>
            `,
    });

    expect(".o-map-renderer--pin-list-group-header").toHaveCount(0, {
        message: "Should not have any groups",
    });

    await toggleSearchBarMenu();

    // don't throw an error when grouping a field with a false value
    await toggleMenuItem("scheduled_date");
    await toggleMenuItemOption("scheduled_date", "year");
});

test("Check groupBy on properties field", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Partner._fields["properties_definition"] = fields.PropertiesDefinition({
        string: "Properties Definition",
    });
    Task._fields["task_properties"] = fields.Properties({
        string: "Properties",
        definition_record: "partner_id",
        definition_record_field: "properties_definition",
    });
    Partner._records = [
        {
            id: 1,
            name: "Bar",
            partner_latitude: 4.0,
            partner_longitude: 4.5,
            properties_definition: [
                {
                    name: "bd6404492c244cff",
                    type: "char",
                    string: "Reference Number",
                },
            ],
        },
        {
            id: 2,
            name: "Foo",
            partner_latitude: 10.0,
            partner_longitude: 10.5,
            sequence: 3,
            properties_definition: [
                {
                    name: "bd6404492c244cff",
                    type: "char",
                    string: "Reference Number",
                },
            ],
        },
    ];
    Task._records = [
        {
            id: 1,
            name: "FooProject",
            sequence: 1,
            partner_id: 1,
            task_properties: {
                bd6404492c244cff: "1234",
            },
        },
        {
            id: 2,
            name: "BarProject",
            sequence: 2,
            partner_id: 2,
            task_properties: {
                bd6404492c244cff: "5678",
            },
        },
    ];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
        searchViewId: false,
        searchViewArch: `
                <search>
                    <group expand='0' string='Group By'>
                        <filter string="task_properties" name="task_properties"
                            context="{'group_by': 'task_properties'}"/>
                    </group>
                </search>
            `,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(0, {
        message: "Should not have any groups",
    });

    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    await toggleSearchBarMenu();

    // don't throw an error when grouping on a property
    await toggleMenuItem("task_properties");
    await animationFrame();
    await contains(".o_accordion_values .o_menu_item").click();
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    // check that the property has been added in the facet without crashing
    expect(`.o_facet_value:contains("Reference Number")`).toHaveCount(1);
    expect(queryAllTexts(`.o-map-renderer--pin-list-group-header`)).toEqual(["1234", "5678"]);
});

test("Change groupBy", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.threeRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
        searchViewId: false,
        searchViewArch: `
                <search>
                    <filter string="Partner" name="partner_id" context="{'group_by': 'partner_id'}"/>
                    <filter string="Name" name="name" context="{'group_by': 'name'}"/>
                </search>
            `,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(0, {
        message: "Should not have any groups",
    });

    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    await toggleSearchBarMenu();
    await toggleMenuItem("Partner");
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(2, {
        message: "Should have 2 groups",
    });
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["Bar", "Foo"]);
    // Groups should be loaded too
    expect(".o-map-renderer--pin-list-details li").toHaveCount(3);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject\nFooBarProject",
        "BarProject",
    ]);

    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
        await toggleSearchBarMenu();
    }
    await toggleMenuItem("Name");
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["Bar", "Foo"], {
        message: "Should not have changed",
    });
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject\nFooBarProject",
        "BarProject",
    ]);
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
        await toggleSearchBarMenu();
    }
    await toggleMenuItem("Partner");
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(3, {
        message: "Should have 3 groups",
    });
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual([
        "FooProject",
        "BarProject",
        "FooBarProject",
    ]);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject",
        "BarProject",
        "FooBarProject",
    ]);
    expect(".o-map-renderer--pin-list-details:eq(0) li").toHaveCount(1);
    expect(".o-map-renderer--pin-list-details:eq(1) li").toHaveCount(1);
    expect(".o-map-renderer--pin-list-details:eq(2) li").toHaveCount(1);
});

//--------------------------------------------------------------------------
// Controller testing
//--------------------------------------------------------------------------

test("Click on open button opens the form view", async () => {
    mockService("action", {
        doAction(actionRequest) {
            expect.step("switchView");
            expect(actionRequest.views[0]).toEqual([false, "form"], {
                message: "The view switched to should be form",
            });
            expect(actionRequest.res_id).toBe(1, { message: "Res Id should be correct" });
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_footer").toHaveCount(1, {
        message: "The button should be present in the dom",
    });
    await contains(".o_popover_footer .o_open_record_btn").click();
    expect.verifySteps(["switchView"]);
});

test("Middle click on open button open record in tab", async () => {
    mockService("action", {
        doAction(actionRequest, options) {
            expect.step("switchView");
            expect(actionRequest.views[0]).toEqual([false, "form"], {
                message: "The view switched to should be form",
            });
            expect(actionRequest.res_id).toBe(1, { message: "Res Id should be correct" });
            expect(options).toEqual({ newWindow: true });
        },
    });
    Task._views.form = "<form/>";

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        config: { views: [[false, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });

    await contains("div.leaflet-marker-icon").click();
    expect(".o_popover_footer .o_open_record_btn").toHaveCount(1, {
        message: "The button should be present in the dom",
    });
    await contains(".o_popover_footer .o_open_record_btn").click({ ctrlKey: true });
    expect.verifySteps(["switchView"]);
});

test("Test the lack of open button", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"></map>`,
    });

    await contains("div.leaflet-marker-icon").click();

    expect(
        "div.leaflet-popup-pane button.btn.btn-primary.o-map-renderer--popup-buttons-open"
    ).toHaveCount(0, { message: "The button should not be present in the dom" });
});

test("Test using a field other than partner_id for the map view", async () => {
    Task._records = TEST_RECORDS.task.anotherPartnerId;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="another_partner_id"></map>`,
    });

    await contains("div.leaflet-marker-icon").click();

    expect(
        "div.leaflet-popup-pane button.btn.btn-primary.o-map-renderer--popup-buttons-open"
    ).toHaveCount(0, { message: "The button should not be present in the dom" });
});

test("Check Google Maps URL is updating on domain change", async () => {
    Task._records = [
        { id: 1, name: "FooProject", sequence: 1, partner_id: 2 },
        { id: 2, name: "BarProject", sequence: 2, partner_id: 3 },
    ];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"/>`,
        searchViewArch: `
                        <search>
                            <filter name="some_filter" string="FooProject only" domain="[['name', '=', 'FooProject']]"/>
                        </search>`,
    });

    await click("button.btn.btn-secondary");
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&waypoints=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies|Chauss%C3%A9e%20de%20Wavre%2050%2C%201367%2C%20Ramillies",
    ]);

    //apply domain and check that the Google Maps URL on the button reflects the changes
    await toggleSearchBarMenu();
    await toggleMenuItem("FooProject only");
    await click("button.btn.btn-secondary");
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&waypoints=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
    ]);
});

test("Check Google Maps URL (routing and multiple records)", async () => {
    Task._records = [
        { id: 1, name: "FooProject", sequence: 1, partner_id: 2 },
        { id: 2, name: "BarProject", sequence: 2, partner_id: 3 },
    ];

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized"/>`,
    });

    await click("button.btn.btn-secondary");
    expect.verifySteps([
        "https://www.google.com/maps/dir/?api=1&destination=Chauss%C3%A9e%20de%20Wavre%2050%2C%201367%2C%20Ramillies&waypoints=Chauss%C3%A9e%20de%20Namur%2040%2C%201367%2C%20Ramillies",
    ]);
});

test("Do not notify if unmounted after fetching coordinate", async () => {
    const def = Promise.withResolvers();

    patchWithCleanup(Geolocation.prototype, {
        async _fetchCoordinatesFromAddressOSM() {
            return def.promise;
        },
    });
    patchWithCleanup(MapModel.prototype, {
        _notifyFetchedCoordinate() {
            expect.step("notify");
        },
    });

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized"/>`,
    });

    destroyApp();

    def.resolve();
    await animationFrame();

    expect.verifySteps([]);
});

test("Do not fetch if unmounted after waiting interval", async () => {
    patchWithCleanup(Geolocation.prototype, {
        async _fetchCoordinatesFromAddressOSM() {
            expect.step("_fetchCoordinatesFromAddressOSM");
        },
        async geolocatePartners() {
            expect.step("geolocatePartners");
            return super.geolocatePartners(...arguments);
        },
    });
    patchWithCleanup(MapModel.prototype, {
        _notifyFetchedCoordinate() {
            expect.step("_notifyFetchedCoordinate");
        },
    });

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized"/>`,
    });

    destroyApp();
    await animationFrame();

    expect.verifySteps(["geolocatePartners"]);
});

test("Check groupBy on selection field", async () => {
    expect.assertions(1);
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    Task._records = [{ id: 1, name: "Project", sequence: 1, partner_id: 1, task_status: "abc" }];
    onRpc("res.partner", "search_read", () => TEST_RECORDS.partner.twoRecordsAddressCoordinates);

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
        groupBy: ["task_status"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(1, { message: "ABC" });
});

test("display '0' for false group, when grouped by int field", async () => {
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
        searchViewId: false,
        groupBy: ["sequence"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveText("0");
});

test("Map view with default_group_by", async () => {
    Task._records = TEST_RECORDS.task.threeRecords;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map default_group_by="partner_id" res_partner="partner_id" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(2, {
        message: "Should have 2 groups",
    });
    expect(queryAllTexts(".o-map-renderer--pin-list-group-header")).toEqual(["Bar", "Foo"]);
    expect(".o-map-renderer--pin-list-details").toHaveCount(2);
    expect(".o-map-renderer--pin-list-details li").toHaveCount(3);
    expect(queryAllTexts(".o-map-renderer--pin-list-details")).toEqual([
        "FooProject\nFooBarProject",
        "BarProject",
    ]);
});

test("GroupBy on datetime field with no subgroup specified", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    Task._records = TEST_RECORDS.task.twoRecordsFieldDateTime;
    Partner._records = TEST_RECORDS.partner.twoRecordsAddressCoordinates;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map default_group_by="scheduled_date" res_partner="partner_id" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-group-header").toHaveCount(2);
    expect(".o-map-renderer--pin-list-group-header:eq(1)").toHaveText("February 2022", {
        message: "Should default to month scale when not specified",
    });
});

test("Groupby coloring in pin list and marker", async () => {
    // When grouping each group should have it's own marker color
    // On the map and the sidebar list
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"></map>`,
        groupBy: ["partner_id"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    const markers = document.querySelectorAll(".o_map_marker_content svg path");
    expect(markers[0].getAttribute("fill") == markers[1].getAttribute("fill")).toBe(false);

    const sbMarkers = document.querySelectorAll(
        ".o-map-renderer--pin-list-group-header span svg path"
    ); // Sidebar markers
    expect(sbMarkers[0].getAttribute("fill") == sbMarkers[1].getAttribute("fill")).toBe(false);
});

test.tags("desktop");
test("Increase map marker size on task list item hover", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"></map>`,
    });

    expect("div.leaflet-marker-icon.o_map_marker_hover").toHaveCount(0, {
        message: "The marker size should not be increased by default",
    });

    // Hover over the first list item
    await contains("li.o-map-renderer--pin-clickable:eq(0)").hover();
    expect("div.leaflet-marker-icon.o_map_marker_hover").toHaveCount(1, {
        message: "The marker size should increase when hovering over related list item",
    });

    // Move mouse to the body/background
    await contains("div.o_control_panel").hover();
    expect("div.leaflet-marker-icon.o_map_marker_hover").toHaveCount(0, {
        message: "The marker size should come back to normal on exit",
    });
});

test.tags("desktop");
test("Highlight task list item on marker hover", async () => {
    Task._records = TEST_RECORDS.task.twoRecords;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"></map>`,
    });

    expect("li.o-map-renderer--pin-clickable.o_map_pin_hover").toHaveCount(0, {
        message: "No map list item should be highlighted by default",
    });

    // Hover over the first map marker
    await contains("div.leaflet-marker-icon:eq(0)").hover();
    expect("li.o-map-renderer--pin-clickable.o_map_pin_hover").toHaveCount(1, {
        message: "The list item should be highlighted on map marker hover",
    });

    // Move mouse to the body/background
    await contains("div.o_control_panel").hover();
    expect("li.o-map-renderer--pin-clickable.o_map_pin_hover").toHaveCount(0, {
        message: "The list item should come back to normal on map marker hover",
    });
});

test.tags("desktop");
test("Click on a located task list item centers the map and opens its marker's popover", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id"></map>`,
    });
    expect(".leaflet-pane .leaflet-popup-pane > *").toHaveCount(0, {
        message: "The popup div should be empty",
    });

    await contains("li.o-map-renderer--pin-clickable").click();
    await animationFrame();
    expect(".o_map_popover").toHaveCount(1, {
        message: "Clicking the address in the sidebar should open its marker's popover",
    });

    // The popover should stay open, not just flash open before disappearing.
    // This can easily be broken with the Owl 3 migration
    await animationFrame();
    expect(".o_map_popover").toHaveCount(1, {
        message: "The marker's popover should still be open shortly after",
    });
});

test.tags("mobile");
test("View with one record and a partner located by coordinates in mobile", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.coordinatesNoAddress;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect("div.leaflet-marker-icon").toHaveCount(1, {
        message: "There should be one marker on the map",
    });
    expect(".o-map-renderer--pin-list-container").toHaveCount(0);
    await contains(".o-sm-map-toggler button:contains(Locations)").click();
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    await contains(".o-sm-map-toggler button:contains(Locations)").click();
    expect(".o-map-renderer--pin-list-container").toHaveCount(0);
    await contains(".o-sm-map-toggler button:contains(Locations)").click();
    await contains(
        ".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li:first"
    ).click();
    await animationFrame();
    expect(".o-map-renderer--pin-list-container").toHaveCount(0);
    expect(".o_map_popover").toHaveCount(1);
});

test("Create a route including user's position", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback, error) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route, params) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    trips: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [14, 10],
                                                    [10.5, 10],
                                                    [13, 12.5],
                                                    [14, 10],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 5000,
                            distance: 10000,
                        },
                    ],
                });
            }
        },
    });

    Task._records = TEST_RECORDS.task.fourPartners;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        4
    );
    expect("div.leaflet-marker-icon").toHaveCount(5, {
        message: "Should have a marker for the user's position",
    });
    expect("div.leaflet-marker-icon:first path:first").toHaveAttribute("fill", "#007E82", {
        message: "Standard ungrouped marker color",
    });
    expect("div.leaflet-marker-icon:last path:first").toHaveAttribute("fill", "#D6145F", {
        message: "Different color for user position marker",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1);
    expect(".leaflet-tooltip-pane .leaflet-tooltip").toHaveText("10 km in 1h 23m", {
        message: "A leaflet tooltip should appear",
    });
    expect(".o_content .o-autocomplete input").toHaveValue("Your location");
    expect.verifySteps([
        "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/14,10;10.5,10;11.5,11;12.5,12;13,12.5;14,10?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
    ]);
});

test("Create a route including user's position (ordered routing)", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback, error) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route, params) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    routes: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [14, 10],
                                                    [10.5, 10],
                                                    [13, 12.5],
                                                    [14, 10],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 5000,
                            distance: 10000,
                        },
                    ],
                });
            }
        },
    });

    Task._records = TEST_RECORDS.task.fourPartners;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    const view = await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="ordered" />`,
    });
    const controller = getMapController(view);
    expect(controller.model.metaData.routing).toBe("ordered", {
        message: "The routing option should be enabled",
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        4
    );
    expect("div.leaflet-marker-icon").toHaveCount(5, {
        message: "Should have a marker for the user's position",
    });
    expect("div.leaflet-marker-icon:first path:first").toHaveAttribute("fill", "#007E82", {
        message: "Standard ungrouped marker color",
    });
    expect("div.leaflet-marker-icon:last path:first").toHaveAttribute("fill", "#D6145F", {
        message: "Different color for user position marker",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1);
    expect(".leaflet-tooltip-pane .leaflet-tooltip").toHaveText("10 km in 1h 23m", {
        message: "A leaflet tooltip should appear",
    });
    expect(".o_content .o-autocomplete input").toHaveValue("Your location");
    expect.verifySteps([
        "https://api.mapbox.com/directions/v5/mapbox/driving/14,10;10.5,10;11.5,11;12.5,12;13,12.5;14,10?access_token=token&steps=true&geometries=geojson",
    ]);
});

test("Create a route including user's position (grouped case)", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback, error) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route, params) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    trips: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [14, 10],
                                                    [10.5, 10],
                                                    [13, 12.5],
                                                    [14, 10],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 5000,
                            distance: 10000,
                        },
                    ],
                });
            }
        },
    });

    Task._records = TEST_RECORDS.task.fourPartners;
    Partner._records = TEST_RECORDS.partner.fourRecords;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
        groupBy: ["name"],
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        4
    );
    expect("div.leaflet-marker-icon").toHaveCount(5, {
        message: "Should have a marker for the user's position",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(2, {
        message: "Generates one route per group",
    });
    expect(".o_content .o-autocomplete input").toHaveValue("Your location");
    expect.verifySteps(
        [
            "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/14,10;10.5,10;12.5,12;14,10?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
            "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/14,10;11.5,11;13,12.5;14,10?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
        ],
        { message: "User position is always used as starting point for all routes" }
    );
});

test("User position falls back to active company position if no permission", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "denied" };
        },
    });

    onRpc("res.company", "web_read", ({ args, kwargs }) => {
        expect(args[0][0]).toBe(1);
        expect(kwargs.specification).toEqual({
            partner_id: {
                fields: {
                    contact_address_complete: {},
                    partner_latitude: {},
                    partner_longitude: {},
                },
            },
        });
        expect.step("Read company");
        return [
            {
                partner_id: {
                    contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                    partner_latitude: 10,
                    partner_longitude: 15,
                },
            },
        ];
    });

    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route, params) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    trips: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [15, 10],
                                                    [10.5, 10],
                                                    [15, 10],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 3000,
                            distance: 3000,
                        },
                    ],
                });
            }
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    expect("div.leaflet-marker-icon").toHaveCount(2, {
        message: "Should have a marker for the user's position",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1, {
        message: "Should create a route even with one record since there's the company position",
    });
    expect(".leaflet-tooltip-pane .leaflet-tooltip").toHaveText("3 km in 50m", {
        message: "A leaflet tooltip should appear",
    });
    expect(".o_content .o-autocomplete input").toHaveValue("Chaussée de Namur 40, 1367, Ramillies");
    expect.verifySteps([
        "Read company",
        "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/15,10;10.5,10;15,10?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
    ]);
});

test("Localisation denied initially and active company data unavailable, give permission and locate user", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
    let permission = "denied";
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: permission };
        },
    });
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback, error) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
    });

    mockService("http", {
        get: (route, params) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    trips: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [14, 10],
                                                    [10.5, 10],
                                                    [14, 10],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 2400,
                            distance: 2500,
                        },
                    ],
                });
            }
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    expect("div.leaflet-marker-icon").toHaveCount(1);
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    expect(".o_content .o-autocomplete input").toHaveValue("");
    expect.verifySteps([]);
    // Allow localization and click on the user localization button
    permission = "granted";
    await contains(".o_content [data-icon='my_location']").click();
    expect(".o-map-renderer--pin-list-container .o-map-renderer--pin-list-details li").toHaveCount(
        1
    );
    expect("div.leaflet-marker-icon").toHaveCount(2, {
        message: "Should have a marker for the user's position",
    });
    expect(".leaflet-overlay-pane path").toHaveCount(1, {
        message: "Should create a route even with one record since there's the user's position",
    });
    expect(".leaflet-tooltip-pane .leaflet-tooltip").toHaveText("2.5 km in 40m", {
        message: "A leaflet tooltip should appear",
    });
    expect(".o_content .o-autocomplete input").toHaveValue("Your location");
    expect.verifySteps([
        "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/14,10;10.5,10;14,10?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
    ]);
    // Disable localization by pressing the button again
    await contains(".o_content [data-icon='my_location']").click();
    expect("div.leaflet-marker-icon").toHaveCount(1);
    expect(".leaflet-overlay-pane path").toHaveCount(0);
    expect(".o_content .o-autocomplete input").toHaveValue("");
    expect.verifySteps([]);
});

test("Address autocomplete shows hint when fewer than 3 characters are typed", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    await contains(".o_map_address_autocomplete input").fill("ab", { confirm: false });
    await advanceTime(500);
    await waitFor(".o-autocomplete--dropdown-item");
    expect(".o-autocomplete--dropdown-item").toHaveCount(1);
    expect(".o-autocomplete--dropdown-item").toHaveText("Start typing 3 characters");
});

test("Address autocomplete queries model and shows results at 3+ characters", async () => {
    patchWithCleanup(Geolocation.prototype, {
        async searchCoordinatesFromAddress() {
            return [
                { address: "Rue de la Loi 1, Bruxelles", latitude: 50.8, longitude: 4.36 },
                { address: "Rue de la Paix 1, Paris", latitude: 48.87, longitude: 2.33 },
            ];
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    await contains(".o_map_address_autocomplete input").fill("rue", { confirm: false });
    await advanceTime(500);
    await waitFor(".o-autocomplete--dropdown-item");
    expect(".o-autocomplete--dropdown-item").toHaveCount(2);
    expect(".o-autocomplete--dropdown-item:first").toHaveText("Rue de la Loi 1, Bruxelles");
    expect(".o-autocomplete--dropdown-item:first").toHaveClass("o_map_address_result");
});

test("my_location button hides and search icon appears when typing in address input", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    expect(".o_content [data-icon='my_location']").toBeVisible();
    expect(".o_content [data-icon='search']").toHaveCount(0);

    await contains(".o_map_address_autocomplete input").fill("pa", { confirm: false });
    await animationFrame();
    expect(".o_content [data-icon='my_location']").not.toBeVisible();
    expect(".o_content [data-icon='search']").toHaveCount(1);
});

test("User position pin popup shows address and Navigate to button for address-based position", async () => {
    patchWithCleanup(MapModel.prototype, {
        async _fetchUserPosition(data) {
            data.userPosition = {
                address: "Chaussée de Namur 40, 1367, Ramillies",
                latitude: 50.6,
                longitude: 4.9,
            };
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });

    // The last marker is the user position pin
    await contains(".leaflet-marker-icon:last").click();
    expect(".leaflet-popup-pane .o-map-renderer--popup-table tbody tr").toHaveCount(1);
    expect(".leaflet-popup-pane tbody .o-map-renderer--popup-table-content-name").toHaveText(
        "Address"
    );
    expect(".leaflet-popup-pane tbody .o-map-renderer--popup-table-content-value").toHaveText(
        "Chaussée de Namur 40, 1367, Ramillies"
    );
    expect(".leaflet-popup-pane .o-map-renderer--popup-buttons a").toHaveCount(1);
    expect(".leaflet-popup-pane .o-map-renderer--popup-buttons a").toHaveText("Navigate to");
    expect(".leaflet-popup-pane .o-map-renderer--popup-buttons button").toHaveCount(0);
});

test("User position pin popup shows only label for GPS-only position (no Navigate to)", async () => {
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    await contains("div.leaflet-marker-icon:last").click();
    expect(".leaflet-popup-pane tbody .o-map-renderer--popup-table-content-value").toHaveText(
        "Your location"
    );
    expect(".leaflet-popup-pane .o-map-renderer--popup-buttons").toHaveCount(0);
});

test.tags("desktop");
test("Hovering user position pin highlights the address input", async () => {
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    expect(".o_map_address_autocomplete").not.toHaveClass("o_map_address_hover");
    await contains("div.leaflet-marker-icon:last").hover();
    expect(".o_map_address_autocomplete").toHaveClass("o_map_address_hover");
});

test.tags("desktop");
test("User position change correctly triggers a map update", async () => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });

    patchWithCleanup(Geolocation.prototype, {
        fetchRoute: UNPATCHED_FETCH_ROUTE,
        async _fetchCoordinatesFromAddressMB() {
            return [{ latitude: 11.0, longitude: 12.0 }];
        },
    });

    patchWithCleanup(MapModel.prototype, {
        _notifyFetchedCoordinate(data) {
            expect.step("notify");
            return super._notifyFetchedCoordinate(data);
        },
    });

    onRpc("res.company", "web_read", () => {
        expect.step("Read company");
        return [
            {
                partner_id: {
                    contact_address_complete: "Chaussée de Namur 40, 1367, Ramillies",
                    partner_latitude: 10,
                    partner_longitude: 15,
                },
            },
        ];
    });

    mockService("http", {
        get: (route) => {
            if (route.includes("api.mapbox.com")) {
                expect.step(route);
                return Promise.resolve({
                    trips: [
                        {
                            legs: [
                                {
                                    steps: [
                                        {
                                            geometry: {
                                                coordinates: [
                                                    [15, 10],
                                                    [10.5, 10],
                                                    [15, 10],
                                                ],
                                            },
                                        },
                                    ],
                                },
                            ],
                            duration: 3000,
                            distance: 3000,
                        },
                    ],
                });
            }
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });
    expect(".o_content .o-autocomplete input").toHaveValue("Chaussée de Namur 40, 1367, Ramillies");
    expect.verifySteps([
        "Read company",
        "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/15,10;10.5,10;15,10?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
        "notify",
    ]);

    await contains(".o_content .o-autocomplete input").edit("Rue du Blé, Belgium");
    expect(".o_content .o-autocomplete input").toHaveValue("Rue du Blé, Belgium");

    await expect.waitForSteps(
        [
            "https://api.mapbox.com/optimized-trips/v1/mapbox/driving/12,11;10.5,10;12,11?access_token=token&roundtrip=false&steps=true&geometries=geojson&source=first&destination=last",
            "notify",
        ],
        { timeout: 500 }
    );
});

test("Click on the New button", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    Task._views = {
        "map,false": `<map res_partner="partner_id" />`,
        "form,false": `<form><field name="name"/></form>`,
        "search,false": `<search/>`,
    };

    onRpc("onchange", () => expect.step("onchange"));
    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        type: "ir.actions.act_window",
        views: [
            [false, "map"],
            [false, "form"],
        ],
    });
    expect("button.o_map_button_add").toHaveCount(1);

    await contains("button.o_map_button_add").click();
    expect.verifySteps(["onchange"]);
    expect(".o_form_view .o_form_editable").toHaveCount(1, {
        message: "should have switched to the form view in edition mode on a new record",
    });
});

test(`No New button when create="false"`, async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" create="false" />`,
    });
    expect("button.o_map_button_add").toHaveCount(0);
});

test("Click on Unlocated item should open the form dialog to avoid lose context", async () => {
    Task._records = TEST_RECORDS.task.recordWithouthPartner;
    mockService("action", {
        doAction(actionRequest) {
            expect(actionRequest.target).toEqual("new", {
                message: "Should open a dialog to edit the record",
            });
            expect(actionRequest.type).toEqual("ir.actions.act_window");
            expect(actionRequest.name).toEqual(TEST_RECORDS.task.recordWithouthPartner[0].name);
            expect(actionRequest.res_id).toBe(TEST_RECORDS.task.recordWithouthPartner[0].id);
            expect(actionRequest.res_model).toEqual(Task._name);
            expect(actionRequest.views[0]).toEqual([false, "form"], {
                message: "The view should be a form",
            });
            expect.step("doAction");
            return super.doAction(...arguments);
        },
    });
    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    await contains(".o-map-renderer--pin-list-group-header:contains(Unlocated)").click();
    await contains(".o_row_task_title").click();
    expect.verifySteps(["doAction"]);
    expect(".o_dialog").toHaveCount(1);
});

test("Click on open button uses the form view id configured on the action", async () => {
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    Task._records = TEST_RECORDS.task.oneRecord;
    Task._views["form,42"] = `<form><field name="name"/></form>`;

    mockService("action", {
        doAction(actionRequest) {
            expect.step("switchView");
            expect(actionRequest.views[0]).toEqual([42, "form"], {
                message: "The form view id defined on the action should be used",
            });
            expect(actionRequest.res_id).toBe(1, { message: "Res Id should be correct" });
        },
    });

    await mountView({
        config: { views: [[42, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" routing="optimized" />`,
    });

    await contains("div.leaflet-marker-icon").click();
    await contains(".o_popover_footer .o_open_record_btn").click();
    expect.verifySteps(["switchView"]);
});

test("Click on open button of a marker with several records uses the list/form views configured on the action", async () => {
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    Task._records = TEST_RECORDS.task.twoRecordOnePartner;
    Task._views["list,55"] = `<list><field name="name"/></list>`;
    Task._views["form,66"] = `<form><field name="name"/></form>`;

    mockService("action", {
        doAction(actionRequest) {
            expect.step("switchView");
            expect(actionRequest.domain).toEqual([["id", "in", [1, 2]]]);
            expect(actionRequest.views).toEqual(
                [
                    [55, "list"],
                    [66, "form"],
                ],
                {
                    message: "The list/form view ids defined on the action should be used",
                }
            );
        },
    });

    await mountView({
        config: {
            views: [
                [55, "list"],
                [66, "form"],
            ],
        },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    await contains("div.leaflet-marker-icon").click();
    await contains(".o_popover_footer .o_open_record_btn").click();
    expect.verifySteps(["switchView"]);
});

test("Click on Unlocated item opens the form dialog using the form view id configured on the action", async () => {
    Task._records = TEST_RECORDS.task.recordWithouthPartner;
    Task._views["form,77"] = `<form><field name="name"/></form>`;

    mockService("action", {
        doAction(actionRequest) {
            expect(actionRequest.views[0]).toEqual([77, "form"], {
                message: "The form view id defined on the action should be used",
            });
            expect.step("doAction");
            return super.doAction(...arguments);
        },
    });
    await mountView({
        config: { views: [[77, "form"]] },
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });
    if (isSmall()) {
        await contains(".o-sm-map-toggler button:contains(Locations)").click();
    }
    await contains(".o-map-renderer--pin-list-group-header:contains(Unlocated)").click();
    await contains(".o_row_task_title").click();
    expect.verifySteps(["doAction"]);
});
test.tags("desktop");
test("Searched address is kept when switching away from the map view and back", async () => {
    patchWithCleanup(Geolocation.prototype, {
        async searchCoordinatesFromAddress() {
            return [{ address: "Rue de la Loi 1, Bruxelles", latitude: 50.8, longitude: 4.36 }];
        },
    });
    onRpc("has_group", () => true);

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    Task._views = {
        "map,false": `<map res_partner="partner_id" />`,
        "list,false": `<list><field name="name"/></list>`,
        "search,false": `<search/>`,
    };

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        type: "ir.actions.act_window",
        views: [
            [false, "map"],
            [false, "list"],
        ],
    });

    await contains(".o_map_address_autocomplete input").fill("rue", { confirm: false });
    await advanceTime(500);
    await waitFor(".o-autocomplete--dropdown-item");
    await contains(".o-autocomplete--dropdown-item:first").click();
    expect(".o_map_address_autocomplete input").toHaveValue("Rue de la Loi 1, Bruxelles");

    await getService("action").switchView("list");
    expect(".o_list_view").toHaveCount(1);
    await getService("action").switchView("map");

    expect(".o_map_address_autocomplete input").toHaveValue("Rue de la Loi 1, Bruxelles", {
        message: "The searched address should survive switching to another view and back",
    });
});

test.tags("desktop");
test("Group fold state is kept when switching away from the map view and back", async () => {
    onRpc("has_group", () => true);

    Task._records = [
        ...TEST_RECORDS.task.threeRecords,
        { id: 4, name: "BazProject", sequence: 4, partner_id: 3 },
    ];
    Partner._records = [
        ...TEST_RECORDS.partner.twoRecordsAddressCoordinates,
        { id: 3, name: "Baz" },
    ];
    Task._views = {
        "map,false": `<map default_group_by="partner_id" res_partner="partner_id" />`,
        "list,false": `<list><field name="name"/></list>`,
        "search,false": `<search/>`,
    };

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        type: "ir.actions.act_window",
        views: [
            [false, "map"],
            [false, "list"],
        ],
    });

    expect(".o-map-renderer--pin-list-group-header").toHaveCount(3, {
        message: "2 groups and the Unlocated section",
    });
    expect(".o-map-renderer--pin-list-details").toHaveCount(2);

    await contains(".o-map-renderer--pin-list-group-header:eq(1)").click();
    expect(".o-map-renderer--pin-list-details").toHaveCount(1);

    await contains(".o-map-renderer--pin-list-group-header:eq(2)").click();
    expect(".o-map-renderer--pin-list-details").toHaveCount(2, {
        message: "The Unlocated section should now be expanded",
    });
    expect(queryAllAttributes(".o-map-renderer--pin-list-group-header .oi-fw", "data-icon")).toEqual(
        ["arrow_drop_down", "arrow_right", "arrow_drop_down"]
    );

    await getService("action").switchView("list");
    expect(".o_list_view").toHaveCount(1);
    await getService("action").switchView("map");

    expect(".o-map-renderer--pin-list-group-header").toHaveCount(3);
    expect(queryAllAttributes(".o-map-renderer--pin-list-group-header .oi-fw", "data-icon")).toEqual(
        ["arrow_drop_down", "arrow_right", "arrow_drop_down"],
        {
            message:
                "The folded group and the expanded Unlocated section should keep their state after switching to another view and back",
        }
    );
});

test("Geolocated user position is stored in localStorage as a lookup marker, not raw coordinates", async () => {
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback) {
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    patchWithCleanup(browser.localStorage, {
        setItem: (key, value) => {
            if (key.includes("map_user_position")) {
                expect.step(value);
            }
        },
    });

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    expect.verifySteps([JSON.stringify({ useBrowserLocation: true })]);
});

test("Browser-based user position is looked up again instead of being reused from localStorage when switching away and back", async () => {
    patchWithCleanup(navigator.permissions, {
        query() {
            return { state: "granted" };
        },
    });
    patchWithCleanup(navigator.geolocation, {
        getCurrentPosition(callback) {
            expect.step("getCurrentPosition");
            callback({ coords: { longitude: 14.0, latitude: 10.0 } });
        },
    });
    onRpc("has_group", () => true);

    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;
    Task._views = {
        "map,false": `<map res_partner="partner_id" />`,
        "list,false": `<list><field name="name"/></list>`,
        "search,false": `<search/>`,
    };

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        res_model: "project.task",
        type: "ir.actions.act_window",
        views: [
            [false, "map"],
            [false, "list"],
        ],
    });
    expect.verifySteps(["getCurrentPosition"]);

    await getService("action").switchView("list");
    expect(".o_list_view").toHaveCount(1);
    await getService("action").switchView("map");

    expect.verifySteps(["getCurrentPosition"], {
        message:
            "The browser location should be looked up again rather than reused from the cached coordinates in localStorage",
    });
});

test.tags("desktop");
test("Pin list sidebar can be resized", async () => {
    Task._records = TEST_RECORDS.task.oneRecord;
    Partner._records = TEST_RECORDS.partner.oneLocatedRecord;

    await mountView({
        type: "map",
        resModel: "project.task",
        arch: `<map res_partner="partner_id" />`,
    });

    const sidebar = queryFirst(".o-map-renderer--pin-list-container");
    const resizeHandle = queryFirst(".o-map-renderer--pin-list-resize");
    const originalWidth = sidebar.offsetWidth;

    const { drop } = await drag(resizeHandle);
    await drop(resizeHandle, { position: { x: -300 }, relative: true });
    expect(sidebar.offsetWidth).toBeGreaterThan(originalWidth, {
        message: "Dragging the resize handle towards the map should widen the sidebar",
    });
});
