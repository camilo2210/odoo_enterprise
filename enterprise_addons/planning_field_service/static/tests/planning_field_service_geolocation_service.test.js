import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { advanceTime, freezeTime } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { startServer } from "@mail/../tests/mail_test_helpers";
import {
    getService,
    mountWebClient,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { definePlanningFieldServiceModels } from "./planning_field_service_mock_models";

const { DateTime } = luxon;

definePlanningFieldServiceModels();

beforeEach(() => {
    mockDate("2026-01-04 12:00:00", 0);
    freezeTime();

    onRpc(({ model, method }) => {
        if (method === "update_resource_live_location") {
            expect(model).toBe("res.users");
            expect.step(method);
            return true;
        } else if (method === "erase_resource_live_location") {
            expect(model).toBe("res.users");
            expect.step(method);
            return true;
        }
    });
    patchWithCleanup(navigator.geolocation, {
        watchPosition(callback) {
            expect.step("watch started");
            callback({
                coords: {
                    latitude: 50.2,
                    longitude: 4.9,
                },
            });
            return 123;
        },
        clearWatch() {
            expect.step("watch stopped");
        },
    });
});

describe.current.tags("desktop");

test("There should only be one watch started per user", async () => {
    let watchId = 123;
    patchWithCleanup(navigator.geolocation, {
        watchPosition(callback) {
            expect.step("watch started");
            callback({
                coords: {
                    latitude: 50.2,
                    longitude: 4.9,
                },
            });
            return watchId++;
        },
    });

    await mountWebClient();
    const geolocationService = getService("field_service_geolocation");

    geolocationService.startWatch();
    await expect.waitForSteps(["watch started", "update_resource_live_location"], {
        message: "A geolocation watch should be started",
    });
    expect(geolocationService.watchId).toBe(123);
    expect(geolocationService.currentPosition).toMatchObject({
        latitude: 50.2,
        longitude: 4.9,
    });

    geolocationService.startWatch();
    expect.verifySteps([], { message: "There should not be any other watch started" });
    expect(geolocationService.watchId).toBe(123);
    expect(geolocationService.currentPosition).toMatchObject({
        latitude: 50.2,
        longitude: 4.9,
    });
});

test("Geolocation watch should be correctly stopped and live location should be erased", async () => {
    const pyEnv = await startServer();
    const resourceId = pyEnv["resource.resource"].create({ name: "Someone" });

    onRpc(({ model, method, args, parent }) => {
        if (method === "update_resource_live_location") {
            pyEnv["resource.resource"].write([resourceId], {
                live_latitude: args[0],
                live_longitude: args[1],
                live_location_last_update: DateTime.now(),
            });
            return parent();
        } else if (method === "should_erase_live_location") {
            expect(model).toBe("res.users");
            expect.step(method);
            return true;
        } else if (method === "erase_resource_live_location") {
            pyEnv["resource.resource"].write([resourceId], {
                live_latitude: false,
                live_longitude: false,
                live_location_last_update: false,
            });
            return parent();
        }
    });

    await mountWebClient();
    const geolocationService = getService("field_service_geolocation");

    const resource = pyEnv["resource.resource"].browse(resourceId)[0];
    expect(!!resource.live_latitude).toBe(false);
    expect(!!resource.live_longitude).toBe(false);
    expect(!!resource.live_location_last_update).toBe(false);

    geolocationService.startWatch();
    await expect.waitForSteps(["watch started", "update_resource_live_location"], {
        message: "A geolocation watch should be started",
    });
    expect(geolocationService.watchId).toBe(123);
    expect(resource.live_latitude).toBe(50.2);
    expect(resource.live_longitude).toBe(4.9);
    expect(resource.live_location_last_update).toMatchObject(DateTime.now());

    await geolocationService.stopWatch();
    await expect.waitForSteps(
        ["should_erase_live_location", "watch stopped", "erase_resource_live_location"],
        {
            message: "The watch should be stopped and the live location should be erased",
        }
    );
    expect(geolocationService.watchId).toBe(null);
    expect(geolocationService.currentPosition).toMatchObject({});
    expect(!!resource.live_latitude).toBe(false);
    expect(!!resource.live_longitude).toBe(false);
    expect(!!resource.live_location_last_update).toBe(false);
});

test("Geolocation watch should be stopped if the resource has finished his day", async () => {
    let [latitude, longitude] = [50, 4];
    let intervalId;
    patchWithCleanup(navigator.geolocation, {
        watchPosition(callback) {
            expect.step("watch started");
            const sendUpdate = () => {
                callback({
                    coords: {
                        latitude: latitude++,
                        longitude: longitude--,
                    },
                });
            };
            sendUpdate();
            intervalId = setInterval(sendUpdate, 5000);
            return 123;
        },
        clearWatch() {
            expect.step("watch stopped");
            if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
            }
        },
    });
    onRpc(({ model, method }) => {
        if (method === "update_resource_live_location") {
            expect(model).toBe("res.users");
            expect.step(method);
            // if more than 10 seconds we stop the timer
            // this mimics the 1 hour delay defined on the server side
            return (
                DateTime.now().diff(DateTime.fromSQL("2026-01-04 12:00:00"), "seconds").seconds < 10
            );
        }
    });

    await mountWebClient();
    const geolocationService = getService("field_service_geolocation");

    geolocationService.startWatch();
    await expect.waitForSteps(["watch started", "update_resource_live_location"], {
        message: "A geolocation watch should be started",
    });
    expect(geolocationService.currentPosition).toMatchObject({
        latitude: 50,
        longitude: 4,
    });

    // After 5 seconds, geolocation is updated
    advanceTime(5000);
    await expect.waitForSteps(["update_resource_live_location"], {
        message: "The watch should not be stopped",
    });
    expect(geolocationService.currentPosition).toMatchObject({
        latitude: 51,
        longitude: 3,
    });

    // After 10 seconds, geolocation is updated, watch is stopped, and geolocation is erased
    advanceTime(5000);
    await expect.waitForSteps(
        ["update_resource_live_location", "watch stopped", "erase_resource_live_location"],
        {
            message:
                "The watch should be stopped automatically and the geolocation should be erased",
        }
    );
    expect(geolocationService.currentPosition).toMatchObject({});
});
