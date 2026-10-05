import {
    animationFrame,
    expect,
    getFixture,
    manuallyDispatchProgrammaticEvent,
    mockUserAgent,
    test,
} from "@odoo/hoot";
import { Component, useProps, signal, types as t, xml } from "@odoo/owl";
import {
    clickSave,
    contains,
    defineModels,
    destroyApp,
    fields,
    models,
    mountView,
    mountWithCleanup,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { Popover } from "@web/core/popover/popover";
import { user } from "@web/core/user";
import { useBackButton } from "@web/core/utils/hooks";
import { accountMethodsForMobile } from "@web_mobile/js/core/mixins";
import { methods as mobileNativeMethods } from "@web_mobile/js/services/core";

const MY_IMAGE =
    "iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg==";
const BASE64_SVG_IMAGE =
    "PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHdpZHRoPScxNzUnIGhlaWdodD0nMTAwJyBmaWxsPScjMDAwJz48cG9seWdvbiBwb2ludHM9JzAsMCAxMDAsMCA1MCw1MCcvPjwvc3ZnPg==";
const BASE64_PNG_HEADER = "iVBORw0KGg";

class Users extends models.Model {
    name = fields.Char();
}

defineModels([Users]);

test.tags("mobile");
test("component should receive a backbutton event", async () => {
    mockUserAgent("android");
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });

    class DummyComponent extends Component {
        static template = xml`<div/>`;

        setup() {
            useBackButton(this.onBack.bind(this));
        }

        onBack(ev) {
            expect.step(`${ev.type} event`);
        }
    }

    await mountWithCleanup(DummyComponent);
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    expect.verifySteps(["overrideBackButton: true", "backbutton event"]);
    destroyApp();
    expect.verifySteps(["overrideBackButton: false"]);
});

test.tags("mobile");
test("multiple components should receive backbutton events in the right order", async () => {
    mockUserAgent("android");
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });

    class DummyComponent extends Component {
        static template = xml`<div t-out="this.props.name" />`;

        props = useProps({ name: t.string() });

        setup() {
            useBackButton(this.onBack.bind(this));
        }

        onBack(ev) {
            expect.step(`${this.props.name}: ${ev.type} event`);
            dummies().delete(this.props.name);
        }
    }

    class Parent extends Component {
        static components = { DummyComponent };
        static template = xml`
            <t t-foreach="this.dummies()" t-as="name" t-key="name">
                <DummyComponent name="name" />
            </t>
        `;

        dummies = dummies;
    }

    const dummies = signal.Set(new Set());

    await mountWithCleanup(Parent);
    // Need to be added 1 by 1 because Owl mounts siblings from last to first
    dummies().add("dummy1");
    await animationFrame();
    dummies().add("dummy2");
    await animationFrame();
    dummies().add("dummy3");
    await animationFrame();

    // simulate 'backbutton' events triggered by the app
    await manuallyDispatchProgrammaticEvent(document, "backbutton");
    await animationFrame();
    await manuallyDispatchProgrammaticEvent(document, "backbutton");
    await animationFrame();
    await manuallyDispatchProgrammaticEvent(document, "backbutton");
    await animationFrame();

    expect.verifySteps([
        "overrideBackButton: true",
        "dummy3: backbutton event",
        "dummy2: backbutton event",
        "dummy1: backbutton event",
        "overrideBackButton: false",
    ]);
});

test.tags("mobile");
test("component should receive a backbutton event: custom activation", async () => {
    mockUserAgent("android");
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });

    class DummyComponent extends Component {
        static template = xml`<button class="dummy" t-out="this.show()" t-on-click="this.toggle" />`;

        props = useProps({ show: t.boolean() });
        show = signal(this.props.show);

        setup() {
            useBackButton(this.onBack.bind(this), this.show);
        }

        onBack(ev) {
            expect.step(`${ev.type} event`);
        }

        toggle() {
            this.show.set(!this.show());
        }
    }

    await mountWithCleanup(DummyComponent, { props: { show: false } });
    // shouldn't have enabled back button mount
    expect.verifySteps([]);
    await contains(".dummy").click();
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    await contains(".dummy").click();
    // should have enabled/disabled the back button override
    expect.verifySteps([
        "overrideBackButton: true",
        "backbutton event",
        "overrideBackButton: false",
    ]);
    destroyApp();

    // enabled at mount
    await mountWithCleanup(DummyComponent, { props: { show: true } });
    // shouldn't have enabled back button at mount
    expect.verifySteps(["overrideBackButton: true"]);
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));
    destroyApp();
    // should have disabled the back-button override during unmount
    expect.verifySteps(["backbutton event", "overrideBackButton: false"]);
});

test.tags("mobile");
test("popover is closable with backbutton event", async () => {
    mockUserAgent("android");
    patchWithCleanup(mobileNativeMethods, {
        overrideBackButton({ enabled }) {
            expect.step(`overrideBackButton: ${enabled}`);
        },
    });
    class Comp extends Component {
        static template = xml`<div id="comp">in popover</div>`;
    }
    await mountWithCleanup(Popover, {
        props: {
            target: getFixture(),
            position: "bottom",
            component: Comp,
            close: () => destroyApp(),
        },
    });
    await animationFrame();
    expect(".o_popover").toHaveCount(1);
    expect(".o_popover #comp").toHaveCount(1);
    expect.verifySteps(["overrideBackButton: true"]);
    // simulate 'backbutton' event triggered by the app
    document.dispatchEvent(new Event("backbutton"));

    expect.verifySteps(["overrideBackButton: false"]);

    expect(".o_popover").toHaveCount(0);
    expect(".o_popover #comp").toHaveCount(0);
});

test("controller should call native updateAccount method with SVG avatar when saving record", async () => {
    patchWithCleanup(mobileNativeMethods, {
        updateAccount(options) {
            const { avatar, name, username } = options;
            expect.step("should call updateAccount");
            expect(avatar.startsWith(BASE64_PNG_HEADER)).toBe(true, {
                message: "should have a PNG base64 encoded avatar",
            });
            expect(name).toBe("Marc Demo");
            expect(username).toBe("demo");
        },
    });

    patchWithCleanup(user, { login: "demo", name: "Marc Demo" });

    patchWithCleanup(accountMethodsForMobile, {
        url(path) {
            if (path === "/web/image") {
                return `data:image/svg+xml;base64,${BASE64_SVG_IMAGE}`;
            }
            return super.url(...arguments);
        },
    });

    await mountView({
        type: "form",
        resModel: "users",
        arch: `
            <form js_class="res_users_preferences_form">
                <sheet>
                    <field name="name"/>
                </sheet>
            </form>`,
    });

    await clickSave();
    expect.verifySteps(["should call updateAccount"]);
});

test("controller should call native updateAccount method when saving record", async () => {
    patchWithCleanup(mobileNativeMethods, {
        async updateAccount(options) {
            const { avatar, name, username } = options;
            expect.step("should call updateAccount");
            expect(avatar.startsWith(BASE64_PNG_HEADER)).toBe(true, {
                message: "should have a PNG base64 encoded avatar",
            });
            expect(name).toBe("Marc Demo");
            expect(username).toBe("demo");
        },
    });
    patchWithCleanup(user, { login: "demo", name: "Marc Demo" });
    patchWithCleanup(accountMethodsForMobile, {
        url(path) {
            if (path === "/web/image") {
                return `data:image/png;base64,${MY_IMAGE}`;
            }
            return super.url(...arguments);
        },
    });

    await mountView({
        type: "form",
        resModel: "users",
        arch: `
            <form js_class="res_users_preferences_form">
                <sheet>
                    <field name="name"/>
                </sheet>
            </form>`,
    });

    await clickSave();
    expect.verifySteps(["should call updateAccount"]);
});
