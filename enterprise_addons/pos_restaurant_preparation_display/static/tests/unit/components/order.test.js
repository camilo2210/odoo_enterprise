import { describe, test, expect, animationFrame } from "@odoo/hoot";
import { Component, signal, xml } from "@odoo/owl";
import { definePosPrepDisplayModels } from "@pos_enterprise/../tests/unit/data/generate_model_definitions";
import {
    setupPosPrepDisplayEnv,
    createPrepDisplayTicket,
} from "@pos_enterprise/../tests/unit/utils";
import { Order } from "@pos_enterprise/app/components/order/order";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";

const { DateTime } = luxon;

definePosPrepDisplayModels();

describe("order_name", () => {
    test("table without course", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const order = store.filteredOrders[0];
        order.prepOrder.pos_order_id.table_id = { table_number: 1 };
        const comp = await mountWithCleanup(Order, { props: { order } });
        expect(comp.order_name).toBe("T1");
    });

    test("table with course", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const order = store.filteredOrders[0];
        order.prepOrder.pos_order_id.table_id = { table_number: 1 };
        order.course_id = { index: 2, name: "Main Course" };
        const comp = await mountWithCleanup(Order, { props: { order } });
        expect(comp.order_name).toBe("T1 - C2");
    });

    test("table with course allocation shows course name", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const order = store.filteredOrders[0];
        order.prepOrder.pos_order_id.config_id.use_course_allocation = true;
        order.prepOrder.pos_order_id.table_id = { table_number: 1 };
        order.course_id = { index: 2, name: "Main Course" };
        const comp = await mountWithCleanup(Order, { props: { order } });
        expect(comp.order_name).toBe("T1 - Main Course");
    });

    test("no table without course", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const order = store.filteredOrders[0];
        const comp = await mountWithCleanup(Order, { props: { order } });
        expect(comp.order_name).toBe("0001");
    });

    test("no table with course shows course suffix", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const order = store.filteredOrders[0];
        order.course_id = { index: 2, name: "Main Course" };
        const comp = await mountWithCleanup(Order, { props: { order } });
        expect(comp.order_name).toBe("0001 - C2");
    });

    test("no table with course allocation shows course name", async () => {
        const store = await setupPosPrepDisplayEnv();
        await createPrepDisplayTicket(store);
        const order = store.filteredOrders[0];
        order.prepOrder.pos_order_id.config_id.use_course_allocation = true;
        order.course_id = { index: 2, name: "Main Course" };
        const comp = await mountWithCleanup(Order, { props: { order } });
        expect(comp.order_name).toBe("0001 - Main Course");
    });
});

test("duration updated immediately when order transitions from pending to non-pending", async () => {
    const store = await setupPosPrepDisplayEnv();
    await createPrepDisplayTicket(store);

    const order = signal({
        ...store.filteredOrders[0],
        course_id: { fired: false, fired_date: null },
    });
    class Container extends Component {
        static components = { Order };
        static template = xml`<Order order="this.order()"/>`;
        setup() {
            this.order = order;
        }
    }
    await mountWithCleanup(Container);
    expect(".badge.text-bg-warning").toHaveText("Pending");

    const sevenMinutesAgo = DateTime.now().minus({ minutes: 7 });
    order.set({
        ...order(),
        course_id: { fired: true, fired_date: sevenMinutesAgo },
    });
    await animationFrame();

    expect(".o_pdis_alert-timer span").toHaveText("7");
});
