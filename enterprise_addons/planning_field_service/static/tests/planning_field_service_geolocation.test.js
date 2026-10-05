import { beforeEach, expect, test } from "@odoo/hoot";
import { animationFrame, queryAll, waitFor } from "@odoo/hoot-dom";
import { mockDate, runAllTimers } from "@odoo/hoot-mock";
import { clickEvent } from "@web/../tests/views/calendar/calendar_test_helpers";
import {
    contains,
    isSmall,
    mockService,
    mountView,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { SELECTORS } from "@web_gantt/../tests/web_gantt_test_helpers";

import { definePlanningFieldServiceModels } from "./planning_field_service_mock_models";

definePlanningFieldServiceModels();

beforeEach(() => {
    mockDate("2026-01-04 12:00:00", 0);

    patchWithCleanup(navigator.geolocation, {
        watchPosition() {
            expect.step("watch started");
            return 123;
        },
    });
    mockService("field_service_geolocation", {
        getGeolocation: () => true,
    });
    onRpc(({ method, model }) => {
        if (method === "action_sign_in") {
            expect(model).toBe("planning.slot");
            expect.step(method);
            return true;
        } else if (method === "action_complete") {
            expect(model).toBe("planning.slot");
            expect.step(method);
            return true;
        }
    });
});

test("form view: no geolocation watch is started if the setting is disabled", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "planning.group_field_service_allow_geolocation") {
            return false;
        }
    });

    await mountView({
        type: "form",
        resId: 1,
        resModel: "planning.slot",
    });

    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in"]);
    if (isSmall()) {
        await contains("button[title=More]").click();
        await animationFrame();
    }
    await contains("button:contains(Complete)").click();
    await animationFrame();
    expect.verifySteps(["action_complete"]);
});

test("form view: geolocation watch is started on start if the setting is enabled", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "form",
        resId: 1,
        resModel: "planning.slot",
    });

    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in", "watch started"], { ignoreOrder: true });
    if (isSmall()) {
        await contains("button[title=More]").click();
        await animationFrame();
    }
    await contains("button:contains(Complete)").click();
    await animationFrame();
    expect.verifySteps(["action_complete"]);
});

test("form view: geolocation watch is started on complete if the setting is enabled", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "form",
        resId: 1,
        resModel: "planning.slot",
    });

    if (isSmall()) {
        await contains("button[title=More]").click();
        await animationFrame();
    }
    await contains("button:contains(Complete)").click();
    await animationFrame();
    expect.verifySteps(["action_complete", "watch started"], { ignoreOrder: true });
});

test("form view: no geolocation watch is started if the user is not one of the intervention's users", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "form",
        resId: 2,
        resModel: "planning.slot",
    });

    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in"]);
    if (isSmall()) {
        await contains("button[title=More]").click();
        await animationFrame();
    }
    await contains("button:contains(Complete)").click();
    await animationFrame();
    expect.verifySteps(["action_complete"]);
});

test("gantt view: no geolocation watch is started if the setting is disabled", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "planning.group_field_service_allow_geolocation") {
            return false;
        }
    });

    await mountView({
        type: "gantt",
        resModel: "planning.slot",
    });

    await contains(queryAll(SELECTORS.pill)[0]).click();
    await runAllTimers();
    await waitFor(".o_popover");

    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in"]);
});

test("gantt view: geolocation watch is started on start if the setting is enabled", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "gantt",
        resModel: "planning.slot",
    });

    await contains(queryAll(SELECTORS.pill)[0]).click();
    await runAllTimers();
    await waitFor(".o_popover");

    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in", "watch started"], { ignoreOrder: true });
});

test("gantt view: no geolocation watch is started if the user is not one of the intervention's users", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "gantt",
        resModel: "planning.slot",
    });

    await contains(queryAll(SELECTORS.pill)[1]).click();
    await runAllTimers();
    await waitFor(".o_popover");

    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in"]);
});

test("calendar view: no geolocation watch is started if the setting is disabled", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "planning.group_field_service_allow_geolocation") {
            return false;
        }
    });

    await mountView({
        type: "calendar",
        resModel: "planning.slot",
    });

    await clickEvent(1);
    await animationFrame();
    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in"]);
});

test("calendar view: geolocation watch is started on start if the setting is enabled", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "calendar",
        resModel: "planning.slot",
    });

    await clickEvent(1);
    await animationFrame();
    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in", "watch started"], { ignoreOrder: true });
});

test("calendar view: no geolocation watch is started if the user is not one of the intervention's users", async () => {
    onRpc("has_group", () => true);
    await mountView({
        type: "calendar",
        resModel: "planning.slot",
    });

    await clickEvent(2);
    await animationFrame();
    await contains("button:contains(Start)").click();
    await animationFrame();
    expect.verifySteps(["action_sign_in"]);
});
