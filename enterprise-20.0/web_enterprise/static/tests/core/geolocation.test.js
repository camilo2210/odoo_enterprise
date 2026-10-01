import { beforeEach, expect, test } from "@odoo/hoot";
import { Component, xml } from "@odoo/owl";
import {
    destroyApp,
    mockService,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { session } from "@web/session";
import { Geolocation } from "@web_enterprise/core/utils/geolocation";

const MAP_BOX_TOKEN = "token";

async function mountGeolocation() {
    let geolocation;
    class Parent extends Component {
        static template = xml``;
        setup() {
            geolocation = new Geolocation();
        }
    }
    await mountWithCleanup(Parent);
    return geolocation;
}

function makeCoordinates(count) {
    return Array.from({ length: count }, (_, i) => ({
        latitude: 10 + i * 0.01,
        longitude: 10 + i * 0.01,
    }));
}

beforeEach(() => {
    patchWithCleanup(session, { map_box_token: MAP_BOX_TOKEN });
});

test("fetchRoute enforces the MapBox coordinate limit for each routing profile", async () => {
    mockService("notification", {
        add(message, options) {
            expect.step(`notification: ${message}`);
            expect(options).toEqual({ type: "warning" });
        },
    });
    onRpc("https://api.mapbox.com/*", () => {
        expect.step("mapbox request");
        return { trips: [{ id: "trip" }], routes: [{ id: "route" }] };
    });

    const geolocation = await mountGeolocation();

    // The optimization API is limited to 12 addresses.
    expect(await geolocation.fetchRoute(makeCoordinates(13), "optimized")).toBe(null);
    expect.verifySteps(["notification: Routing is limited to 12 addresses"]);

    // The directions API handles more: 13 addresses go through without warning.
    expect(await geolocation.fetchRoute(makeCoordinates(13), "ordered")).toEqual({ id: "route" });
    expect.verifySteps(["mapbox request"]);

    // ...but the directions API still bails out above 25 addresses.
    expect(await geolocation.fetchRoute(makeCoordinates(26), "ordered")).toBe(null);
    expect.verifySteps(["notification: Routing is limited to 25 addresses"]);
});

test("geolocatePartners caches the coordinates even if its owner is destroyed", async () => {
    const requestDeferred = Promise.withResolvers();
    onRpc("https://api.mapbox.com/*", async () => {
        expect.step("mapbox request");
        await requestDeferred.promise;
        return { features: [{ place_name: "Grand-Rosière", geometry: { coordinates: [4, 50] } }] };
    });
    onRpc("res.partner", "update_latitude_longitude", ({ args }) => {
        expect.step("update_latitude_longitude");
        expect(args[0]).toEqual([
            {
                id: 1,
                contact_address_complete: "Grand-Rosière",
                partner_latitude: 50,
                partner_longitude: 4,
            },
        ]);
        return true;
    });

    const geolocation = await mountGeolocation();
    const partner = { id: 1, contact_address_complete: "Grand-Rosière" };
    const geolocated = geolocation.geolocatePartners(partner);
    expect.verifySteps(["mapbox request"]);

    // The owner is destroyed (e.g. switching to another view) before the provider answers.
    destroyApp();
    requestDeferred.resolve();
    await geolocated;

    await expect.waitForSteps(["update_latitude_longitude"]);
});

test("_fetchAddressFromCoordinatesMB picks each field by its place_type, regardless of the features' order or a missing one", async () => {
    onRpc("https://api.mapbox.com/geocoding/v5/*", () => {
        expect.step("mapbox geocoding request");
        return {
            features: [
                // Deliberately out of the usual [address, place, postcode, region, country] order,
                // and missing a "region" feature entirely (e.g. no state/province at these coordinates).
                { place_type: ["country"], text: "Belgium" },
                { place_type: ["postcode"], text: "1000" },
                { place_type: ["address"], text: "Sweet Street", address: "12" },
                { place_type: ["place"], text: "Somewhere" },
            ],
        };
    });

    const geolocation = await mountGeolocation();

    expect(await geolocation._fetchAddressFromCoordinatesMB(38.71, -9.14)).toEqual({
        street: "Sweet Street",
        house_number: "12",
        city: "Somewhere",
        zip: "1000",
        state: undefined,
        country: "Belgium",
    });
    expect.verifySteps(["mapbox geocoding request"]);
});
