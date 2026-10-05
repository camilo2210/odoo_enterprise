import { describe, expect, runAllTimers, test } from "@odoo/hoot";

import { Registerer } from "@voip/core/web/registerer";
import { UserAgent } from "@voip/core/web/user_agent";

import { patchWithCleanup } from "@web/../tests/web_test_helpers";

describe.current.tags("desktop");

function makeVoip() {
    return {
        config: {
            usesOdooProvider: false,
        },
        userAgent: {
            attemptReconnection() {},
        },
        isUnloading: false,
        resolveError() {},
        triggerError() {},
    };
}

test("register recreates only SIP.js registerers stuck waiting", async () => {
    const sipRegisterers = [];
    const addEventListener = window.addEventListener.bind(window);

    class FakeEventEmitter {
        constructor(ownerIndex) {
            this.listeners = new Set();
            this.ownerIndex = ownerIndex;
        }

        addListener(listener) {
            this.listeners.add(listener);
        }

        removeListener(listener) {
            expect.step(`remove listener ${this.ownerIndex}`);
            this.listeners.delete(listener);
        }
    }

    patchWithCleanup(window, {
        addEventListener(type, listener, options) {
            if (type === "beforeunload") {
                return;
            }
            return addEventListener(type, listener, options);
        },
        SIP: {
            Registerer: class {
                constructor(userAgent, options) {
                    this.index = sipRegisterers.length;
                    this.options = options;
                    this.stateChange = new FakeEventEmitter(this.index);
                    this.waiting = this.index === 0;
                    sipRegisterers.push(this);
                }

                dispose() {
                    expect.step(`dispose ${this.index}`);
                    this.disposed = true;
                    return Promise.resolve();
                }

                register() {
                    expect.step(`register ${this.index}`);
                    return Promise.resolve(`registered ${this.index}`);
                }

                unregister() {}
            },
        },
    });

    const registerer = new Registerer(makeVoip(), {});
    const registerPromise = registerer.register();

    expect(registerPromise).toBeInstanceOf(Promise);
    expect(sipRegisterers).toHaveLength(2);
    expect(sipRegisterers[0].disposed).toBe(true);
    expect(sipRegisterers[0].stateChange.listeners.size).toBe(0);
    expect(sipRegisterers[1].options.expires).toBe(Registerer.EXPIRATION_INTERVAL);
    await expect(registerPromise).resolves.toBe("registered 1");

    const healthyRegisterPromise = registerer.register();
    expect(sipRegisterers).toHaveLength(2);
    expect(sipRegisterers[1].disposed).toBe(undefined);
    await expect(healthyRegisterPromise).resolves.toBe("registered 1");
    expect.verifySteps(["remove listener 0", "dispose 0", "register 1", "register 1"]);
});

test("attemptReconnection awaits registration rejection before scheduling retry", async () => {
    patchWithCleanup(Math, { random: () => 0 });
    const userAgent = Object.assign(Object.create(UserAgent.prototype), {
        __sipJsUserAgent: {
            reconnect() {
                expect.step("reconnect");
                return Promise.resolve();
            },
        },
        attemptingToReconnect: false,
        registerer: {
            register() {
                expect.step("register");
                return Promise.reject(new Error("REGISTER request already pending"));
            },
        },
        voip: {
            isUnloading: false,
            resolveError() {
                expect.step("resolve error");
            },
            triggerError() {
                return () => expect.step("resolve error");
            },
        },
    });

    await userAgent.attemptReconnection(2);

    expect(userAgent.attemptingToReconnect).toBe(false);

    userAgent.attemptReconnection = (attemptCount) => expect.step(`retry ${attemptCount}`);
    const elapsedTime = await runAllTimers({ animationFrame: false });

    expect(elapsedTime).toBe(4_000);
    expect.verifySteps(["reconnect", "register", "retry 3"]);
});

test("a successful reconnection preserves active sessions and cancels an obsolete retry", async () => {
    patchWithCleanup(Math, { random: () => 0 });
    const sessions = { ongoing: {} };
    let reconnectFails = true;
    const userAgent = Object.assign(Object.create(UserAgent.prototype), {
        __sipJsUserAgent: {
            reconnect() {
                expect.step("reconnect");
                return reconnectFails
                    ? Promise.reject(new Error("WebSocket unavailable"))
                    : Promise.resolve();
            },
        },
        attemptingToReconnect: false,
        registerer: {
            register() {
                expect.step("register");
                return Promise.resolve();
            },
        },
        sessions,
        voip: {
            isUnloading: false,
            triggerError() {
                return () => expect.step("resolve error");
            },
        },
    });

    await userAgent.attemptReconnection();
    reconnectFails = false;
    await userAgent.attemptReconnection();

    expect(userAgent.sessions).toBe(sessions);
    expect(await runAllTimers({ animationFrame: false })).toBe(0);
    expect.verifySteps(["reconnect", "reconnect", "register", "resolve error"]);
});
