import { test, expect, describe } from "@odoo/hoot";
import { queryOne, waitFor, queryAll } from "@odoo/hoot-dom";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { FloorPlan } from "@pos_restaurant/app/screens/floor_screen/floor_plan/floor_plan";
import { FloorScreen } from "@pos_restaurant/app/screens/floor_screen/floor_screen";
import { setupPosEnv } from "@point_of_sale/../tests/unit/utils";
import { definePosModels } from "@point_of_sale/../tests/unit/data/generate_model_definitions";

const { DateTime } = luxon;

definePosModels();

describe("pos_restaurant_appointment floor_plan.js", () => {
    test("floor_plan.js", async () => {
        const store = await setupPosEnv();
        const fs = await mountWithCleanup(FloorPlan);
        const appointmentOfTable2 = store.models["restaurant.table"].get(2).firstAppointment;
        const appointmentOfTable3 = store.models["restaurant.table"].get(3).firstAppointment;
        expect(appointmentOfTable2.id).toEqual(1);

        expect(appointmentOfTable3.id).toEqual(3);

        expect(fs.isCustomerLate(appointmentOfTable2)).toBe(true);
        expect(fs.isCustomerLate(appointmentOfTable3)).toBe(false);
    });

    test("late customer: appointment label shows time, capacity and name and late timer", async () => {
        const store = await setupPosEnv();
        const table = store.models["restaurant.table"].get(2);
        const appointment = table.firstAppointment;
        appointment.start = DateTime.now().minus({ minutes: 10 });
        await mountWithCleanup(FloorScreen);

        const labelSelector = `.o_fp_table[data-table_id="${table.id}"] .${
            store.env.services.ui.isSmall ? "appointment-info-label" : "appointment-label"
        }`;
        await waitFor(labelSelector);
        const label = queryOne(labelSelector);
        const text = label.textContent.trim();
        expect(text).toInclude(appointment.attendeeName);
        expect(text).toInclude(`[${appointment.waiting_list_capacity}p]`);
        expect(text).toInclude(store.getTime(appointment.start));
        if (store.env.services.ui.isSmall) {
            expect(text).toInclude("10'");
        } else {
            const badgeSelector = `.o_fp_table[data-table_id="${table.id}"] .table-timer-badge`;
            await waitFor(badgeSelector);
            const badge = queryOne(badgeSelector);
            expect(badge.textContent.trim()).toBe("10'");
        }
    });

    test("future appointment: label shows future time, capacity and name, no timer", async () => {
        const store = await setupPosEnv();
        const table = store.models["restaurant.table"].get(2);
        const appointment = table.firstAppointment;
        appointment.start = DateTime.now().plus({ hours: 1 });
        await mountWithCleanup(FloorScreen);

        const labelSelector = `.o_fp_table[data-table_id="${table.id}"] .${
            store.env.services.ui.isSmall ? "appointment-info-label" : "appointment-label"
        }`;
        await waitFor(labelSelector);
        const label = queryOne(labelSelector);
        const text = label.textContent.trim();
        expect(text).toInclude(appointment.attendeeName);
        expect(text).toInclude(`[${appointment.waiting_list_capacity}p]`);
        expect(text).toInclude(store.getTime(appointment.start));
        expect(queryAll(`.o_fp_table[data-table_id="${table.id}"] .table-timer-badge`).length).toBe(
            0
        );
    });
});
