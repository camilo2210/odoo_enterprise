import { expect, test, waitUntil, advanceTime } from "@odoo/hoot";
import { mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { ORM } from "@web/core/orm_plugin";
import { OboxStatus } from "@obox/widgets/obox_status";
import { patch } from "@web/core/utils/patch";

const busHandlers = {};

async function mountStatus({ localAddress, onLoad = () => {} } = {}) {
    mockService("bus_service", {
        addChannel() {},
        subscribe(name, handler) {
            busHandlers[name] = handler;
        },
        unsubscribe() {},
    });
    patch(ORM.prototype, {
        call(model, method) {
            if (model === "obox.obox" && method === "action_check_websocket") {
                expect.step("check websocket");
                return true;
            }
            return super.call(...arguments);
        },
    });
    const record = {
        resId: 1,
        data: {
            internal_websocket_channel: "odoo_token_1",
            external_websocket_channel: "obox_token_1",
            local_address: localAddress,
        },
        async load() {
            onLoad(record);
        },
    };
    const component = await mountWithCleanup(OboxStatus, { props: { record } });
    return { component, record };
}

function mockBox(reachableAddresses) {
    onRpc("/odoo/", async (request) => {
        const address = new URL(request.url).host;
        expect.step(`fetch ${address}`);
        if (!reachableAddresses.includes(address)) {
            throw new Error("unreachable");
        }
        return "ok";
    });
}

test("checks the local network and the websocket when mounted", async () => {
    mockBox(["1.2.3.4:8080"]);

    const { component } = await mountStatus({ localAddress: "1.2.3.4:8080" });
    await waitUntil(() => component.state.lan.lastChecked);

    expect.verifySteps(["check websocket", "fetch 1.2.3.4:8080"]);
    expect(component.state.lan.status).toBe(true);
});

test("an update giving the box its address is checked at once", async () => {
    mockBox(["1.2.3.4:8080"]);
    const { component } = await mountStatus({ localAddress: false });
    await waitUntil(() => component.state.lan.lastChecked);
    expect(component.state.lan.status).toBe(false);
    expect.verifySteps(["check websocket"]);

    const record = component.props.record;
    record.load = async () => {
        record.data.local_address = "1.2.3.4:8080";
    };
    await busHandlers.OBOX_UPDATED({ id: 1 });
    await waitUntil(() => component.state.lan.status);

    expect.verifySteps(["check websocket", "fetch 1.2.3.4:8080"]);
});

test("an update ending after the widget is gone checks nothing", async () => {
    mockBox([]);
    const { component } = await mountStatus({ localAddress: false });
    await waitUntil(() => component.state.lan.lastChecked);
    expect.verifySteps(["check websocket"]);

    const record = component.props.record;
    record.load = async () => {
        component.destroyed = true; // unmounted while the record reloads
    };
    await busHandlers.OBOX_UPDATED({ id: 1 });

    expect.verifySteps([]);
});

test("an update with a new port is checked at once on the new address", async () => {
    mockBox(["1.2.3.4:8081"]);
    const { component } = await mountStatus({ localAddress: "1.2.3.4:8080" });
    await waitUntil(() => component.state.lan.lastChecked);
    expect(component.state.lan.status).toBe(false);
    expect.verifySteps(["check websocket", "fetch 1.2.3.4:8080"]);

    const record = component.props.record;
    record.load = async () => {
        record.data.local_address = "1.2.3.4:8081";
    };
    await busHandlers.OBOX_UPDATED({ id: 1 });
    await waitUntil(() => component.state.lan.status);

    expect.verifySteps(["check websocket", "fetch 1.2.3.4:8081"]);
});

test("an update about another box does not trigger a check", async () => {
    mockBox(["1.2.3.4:8080"]);
    const { component } = await mountStatus({ localAddress: "1.2.3.4:8080" });
    await waitUntil(() => component.state.lan.lastChecked);
    expect.verifySteps(["check websocket", "fetch 1.2.3.4:8080"]);

    await busHandlers.OBOX_UPDATED({ id: 2 });
    await advanceTime(1000);

    expect.verifySteps([]);
});

test("the next periodic check still runs after an update", async () => {
    mockBox(["1.2.3.4:8080"]);
    const { component } = await mountStatus({ localAddress: "1.2.3.4:8080" });
    await waitUntil(() => component.state.lan.lastChecked);

    let lastChecked = component.state.lan.lastChecked;
    await busHandlers.OBOX_UPDATED({ id: 1 });
    await waitUntil(() => component.state.lan.lastChecked !== lastChecked);
    expect.verifySteps([
        "check websocket",
        "fetch 1.2.3.4:8080",
        "check websocket",
        "fetch 1.2.3.4:8080",
    ]);

    lastChecked = component.state.lan.lastChecked;
    await advanceTime(15000);
    await waitUntil(() => component.state.lan.lastChecked !== lastChecked);

    expect.verifySteps(["check websocket", "fetch 1.2.3.4:8080"]);
});

test("a ping from the box marks the websocket as connected", async () => {
    mockBox([]);
    const { component } = await mountStatus({ localAddress: false });
    await waitUntil(() => component.state.wan.lastChecked);
    expect.verifySteps(["check websocket"]);

    busHandlers.PING({ token: "token_1" });

    expect(component.state.wan.status).toBe(true);
});

test("a ping from another box is ignored", async () => {
    mockBox([]);
    const { component } = await mountStatus({ localAddress: false });
    await waitUntil(() => component.state.wan.lastChecked);
    expect.verifySteps(["check websocket"]);

    busHandlers.PING({ token: "token_2" });

    expect(component.state.wan.lastPing).toBe(null);
});
