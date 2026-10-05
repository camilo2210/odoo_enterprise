import { afterEach, beforeEach, describe, expect, test } from "@odoo/hoot";
import { queryAll, queryOne } from "@odoo/hoot-dom";
import { animationFrame, mockDate, mockTimeZone } from "@odoo/hoot-mock";

import { session } from "@web/session";
import {
    clickAllDaySlot,
    moveEventToTime,
    resizeEventToTime,
    selectTimeRange,
} from "@web/../tests/views/calendar/calendar_test_helpers";
import {
    contains,
    defineActions,
    makeMockServer,
    MockServer,
    mountView,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { AppointmentType, defineAppointmentModels } from "./appointment_tests_common";

describe.current.tags("desktop");
defineAppointmentModels();

let userId = session.user_id[0];

// the "Share > New Appointment" menu opens this action to create/edit an
// appointment type; give it a minimal form
AppointmentType._views = {
    form: `<form>
        <field name="name"/>
        <field name="staff_user_ids" widget="many2many_tags"/>
        <field name="category" invisible="1"/>
        <field name="slot_duration"/>
    </form>`,
};
defineActions([
    {
        xml_id: "appointment.appointment_edit_slots_action",
        name: "Configure Appointment",
        res_model: "appointment.type",
        target: "new",
        view_mode: "form",
        views: [[false, "form"]],
        // make sure newly-created appointment types have values that would include them in the sidebar
        // custom + current user included + scheduled by user (which is already the default on the model)
        context: { default_category: "custom", default_staff_user_ids: [userId] },
    },
]);

/**
 * Create a booking page through the "Share > New Appointment" menu, which is also what
 * stores the editor slot duration used to subdivide dragged slots.
 */
async function createBookingPageFromShareMenu(name, { slotDuration } = {}) {
    await openShareMenu();
    await contains(".o-dropdown-item:contains('New Appointment')").click();
    await contains(".o_field_widget[name='name'] input").edit(name);
    if (slotDuration !== undefined) {
        await contains(".o_field_widget[name='slot_duration'] input").edit(String(slotDuration));
    }
    await contains("button.o_form_button_save").click();
    await animationFrame();
}

/**
 * Enter slot edition for a booking page listed in the sidebar. The sidebar lists every
 * appointment type the user manages on each calendar load, so the record must already
 * exist when the view is mounted.
 */
async function editBookingPageFromSidebar(name) {
    await contains(`.o_calendar_filter_item:contains(${name}) button[title="Edit Appointment"]`, {
        visible: false,
    }).click();
    await animationFrame();
}

async function openShareMenu() {
    await contains(".o_appointment_scheduling_box button:contains(Share)").click();
}

const baseTestAppointmentStaffUsers = AppointmentType._records[1].staff_user_ids;
beforeEach(function () {
    userId = session.user_id[0];
    // add user to "Test Appointment"
    AppointmentType._records[1].staff_user_ids = [userId];
    mockDate("2022-01-05 00:00:00");
});
afterEach(function () {
    AppointmentType._records[1].staff_user_ids = baseTestAppointmentStaffUsers;
});

onRpc("res.partner", "get_attendee_detail", () => []);

onRpc("res.users", "has_group", () => true);

onRpc("appointment.type", "has_access", () => true);

onRpc("res.users", "get_calendar_model_data", () => ({
    credential_status: {},
    sync_status: {},
    sync_email: false,
    default_duration: 1,
}));

// one calendar arch for every test; filter_field enables the partner filter that only the
// "only the edited type's events" test toggles (harmless everywhere else)
const CALENDAR_ARCH = `<calendar js_class="attendee_calendar" all_day="allday" date_start="start" date_stop="stop" color="partner_ids">
        <field name="name"/>
        <field name="partner_ids" write_model="calendar.filters" write_field="partner_id" filter_field="active"/>
    </calendar>`;

describe("appointment slot splitting", () => {
    /**
     * return a list of create vals that's expanded as more orm create calls are made
     */
    function captureSlotCreate() {
        const created = [];
        onRpc("appointment.slot", "create", ({ args: [valsList] }) => {
            created.push(...valsList);
        });
        return created;
    }

    /**
     * Create a weekly appointment type (optionally in a specific `appointment_tz`) and enter its
     * slot-edition mode, ready for a drag. Use captureSlotCreate() for the assertions.
     */
    async function editWeeklyType(name, extraVals = {}) {
        const { env: pyEnv } = await makeMockServer();
        pyEnv["appointment.type"].create({
            name,
            category: "recurring",
            staff_user_ids: [userId],
            ...extraVals,
        });
        await mountView({ type: "calendar", resModel: "calendar.event", arch: CALENDAR_ARCH });
        await editBookingPageFromSidebar(name);
    }

    test("custom slots split by the duration set in the wizard", async () => {
        const created = captureSlotCreate();

        await mountView({ type: "calendar", resModel: "calendar.event", arch: CALENDAR_ARCH });

        // with slot duration, when dragging the length should be subdivided in (length / duration) (+ 1 unless exactly divisible)
        await createBookingPageFromShareMenu("Custom Duration Meeting", { slotDuration: 1 });

        await selectTimeRange("2022-01-05 09:00:00", "2022-01-05 11:30:00");
        await animationFrame();

        expect(created).toHaveLength(3);
        expect(created.every((slot) => slot.slot_type === "unique")).toBe(true);
        const spans = created.map((slot) => ({
            start: luxon.DateTime.fromSQL(slot.start_datetime),
            end: luxon.DateTime.fromSQL(slot.end_datetime),
        }));
        // each slot lasts the configured 1h and they are contiguous
        expect(spans.every((s) => s.end.diff(s.start, "hours").hours === 1)).toBe(true);
        expect(spans[1].start.toISO()).toBe(spans[0].end.toISO());
        expect(spans[2].start.toISO()).toBe(spans[1].end.toISO());
    });

    test("custom slots with a zero duration are not subdivided", async () => {
        const created = captureSlotCreate();

        await mountView({ type: "calendar", resModel: "calendar.event", arch: CALENDAR_ARCH });

        // a custom booking page whose slot duration is 0 => no automatic subdivision
        await createBookingPageFromShareMenu("Custom No Duration Meeting", { slotDuration: 0 });

        // a 3h drag stays a single slot spanning the whole range
        await selectTimeRange("2022-01-05 09:00:00", "2022-01-05 12:00:00");
        await animationFrame();

        expect(created).toHaveLength(1);
        expect(created[0].slot_type).toBe("unique");
        const start = luxon.DateTime.fromSQL(created[0].start_datetime);
        const end = luxon.DateTime.fromSQL(created[0].end_datetime);
        expect(end.diff(start, "hours").hours).toBe(3);
    });

    test("extending a slot across the appointment's midnight splits it", async () => {
        // the appointment tz (Honolulu, UTC-10) puts its midnight at the viewer's noon (viewer is
        // UTC+2), so the slot and the boundary it splits at both stay mid-grid, off the flaky edges
        mockTimeZone(2);
        await editWeeklyType("Weekly Meeting", { appointment_tz: "Pacific/Honolulu" });
        // viewer Wed 09:00-11:00 == Honolulu Tue 21:00-23:00: a 2h slot within a single day
        await selectTimeRange("2022-01-05 09:00:00", "2022-01-05 11:00:00");
        await animationFrame();
        const eventId = queryOne(".o_calendar_slot").dataset.eventId;

        const created = captureSlotCreate();
        const writes = [];
        onRpc("appointment.slot", "write", ({ args: [ids] }) => writes.push(ids));

        // drag the end down to viewer 14:00 == Honolulu Wed 02:00, crossing midnight:
        // Tuesday 21:00-24:00 is written, Wednesday 00:00-02:00 is created
        await resizeEventToTime(eventId, "2022-01-05 14:00:00");
        await animationFrame();
        expect(writes).toHaveLength(1);
        expect(created).toHaveLength(1);
        expect(created[0].slot_type).toBe("recurring");
    });

    test("moving a slot across the appointment's midnight splits it", async () => {
        // same Honolulu/viewer-noon setup as the extend test, so the drag stays mid-grid
        mockTimeZone(2);
        await editWeeklyType("Weekly Meeting", { appointment_tz: "Pacific/Honolulu" });
        // viewer Wed 09:00-11:00 == Honolulu Tue 21:00-23:00: a 2h slot within a single day
        await selectTimeRange("2022-01-05 09:00:00", "2022-01-05 11:00:00");
        await animationFrame();
        const eventId = queryOne(".o_calendar_slot").dataset.eventId;

        const created = captureSlotCreate();
        const writes = [];
        onRpc("appointment.slot", "write", ({ args: [ids] }) => writes.push(ids));

        // slide it down 2h so viewer 11:00-13:00 == Honolulu 23:00-01:00, crossing midnight:
        // Tuesday 23:00-24:00 is written, Wednesday 00:00-01:00 is created
        await moveEventToTime(eventId, "2022-01-05 11:00:00");
        await animationFrame();
        expect(writes).toHaveLength(1);
        expect(created).toHaveLength(1);
        expect(created[0].slot_type).toBe("recurring");
    });

    test("the day-boundary split follows the appointment timezone, not the viewer's", async () => {
        const created = captureSlotCreate();
        // appointment midnight = user noon
        mockTimeZone(2);
        await editWeeklyType("Honolulu Meeting", { appointment_tz: "Pacific/Honolulu" });

        // split on crossing midnight, even if it's the middle of the day for the user
        await selectTimeRange("2022-01-05 11:00:00", "2022-01-05 13:00:00");
        await animationFrame();
        expect(created).toHaveLength(2);
        expect(created.every((slot) => slot.slot_type === "recurring")).toBe(true);
        expect(created.map((slot) => slot.weekday)).toEqual(["2", "3"]);

        // crosses midnight in user tz yet it is not split
        created.length = 0;
        await selectTimeRange("2022-01-05 13:00:00", "2022-01-05 15:00:00");
        await animationFrame();
        expect(created).toHaveLength(1);
        expect(created[0].weekday).toBe("3");
    });
});

describe("booking pages sidebar", () => {
    test("clicking the copy button copies the appointment type's url", async () => {
        expect.assertions(2);

        patchWithCleanup(navigator, {
            clipboard: {
                writeText: (value) => {
                    expect(value).toBe(
                        `http://amazing.odoo.com/appointment/2?filter_staff_user_ids=%5B${userId}%5D`
                    );
                },
            },
        });

        onRpc("/appointment/appointment_type/get_calendar_slot_editor_info", () => {
            expect.step("/appointment/appointment_type/get_calendar_slot_editor_info");
        });

        await mountView({
            type: "calendar",
            resModel: "calendar.event",
            arch: CALENDAR_ARCH,
        });

        queryOne(
            '.o_calendar_filter_item:contains("Test Appointment") button[title="Copy invite url to clipboard"]'
        ).click();
        await animationFrame();

        expect.verifySteps(["/appointment/appointment_type/get_calendar_slot_editor_info"]);
    });

    test("create/search anytime appointment type", async () => {
        expect.assertions(6);

        patchWithCleanup(session, { "web.base.url": "http://amazing.odoo.com" });
        patchWithCleanup(navigator, {
            clipboard: {
                writeText: (value) => {
                    expect(value).toBe(
                        `http://amazing.odoo.com/appointment/3?filter_staff_user_ids=%5B${userId}%5D`
                    );
                },
            },
        });

        onRpc("/appointment/appointment_type/search_create_anytime", () => {
            expect.step("/appointment/appointment_type/search_create_anytime");
        });

        await mountView({
            type: "calendar",
            resModel: "calendar.event",
            arch: CALENDAR_ARCH,
        });
        await openShareMenu();
        await contains(".o-dropdown-item:contains('My availabilities')").click();
        await animationFrame();

        expect.verifySteps(["/appointment/appointment_type/search_create_anytime"]);
        expect(MockServer.env["appointment.type"]).toHaveLength(3, {
            message: "Create a new appointment type",
        });

        await openShareMenu();
        await contains(".o-dropdown-item:contains('My availabilities')").click();
        await animationFrame();

        expect.verifySteps(["/appointment/appointment_type/search_create_anytime"]);
        expect(MockServer.env["appointment.type"]).toHaveLength(3, {
            message: "Does not create a new appointment type",
        });
    });

    test("verify share menu and booking pages sidebar are displayed", async () => {
        await mountView({
            type: "calendar",
            resModel: "calendar.event",
            arch: CALENDAR_ARCH,
        });

        expect('.o_appointment_scheduling_box button:contains("Share")').toHaveCount(1);
        expect('.o_cw_filter_label:contains("Booking Pages")').toHaveCount(1);

        await openShareMenu();
        expect(".o-dropdown-item").toHaveCount(3);
        expect(".o-dropdown-item:contains('My availabilities')").toHaveCount(1);
        expect(".o-dropdown-item:contains('One-time link')").toHaveCount(1);
        expect(".o-dropdown-item:contains('New Appointment')").toHaveCount(1);
    });
});

describe("recurring slot rendering", () => {
    async function startEditRecurringSlots({ aptVals = {}, slotValsAll = [] } = {}) {
        const { env: pyEnv } = await makeMockServer();
        const appointmentTypeId = pyEnv["appointment.type"].create({
            name: "Recurring Meeting",
            category: "recurring",
            staff_user_ids: [userId],
            ...aptVals,
        });
        pyEnv["appointment.slot"].create(
            slotValsAll.map((vals) => ({
                appointment_type_id: appointmentTypeId,
                slot_type: "recurring",
                weekday: "1",
                ...vals,
            }))
        );
        await mountView({ type: "calendar", resModel: "calendar.event", arch: CALENDAR_ARCH });
        await editBookingPageFromSidebar("Recurring Meeting");
    }

    test("a recurring slot crossing midnight in the viewer tz renders as two day segments", async () => {
        expect.assertions(3);
        mockTimeZone(2);
        await startEditRecurringSlots({
            aptVals: { appointment_tz: "UTC", appointment_duration: 1, slot_creation_interval: 1 },
            slotValsAll: [{ start_hour: 21, end_hour: 23 }], // straddles midnight in UTC+2
        });

        expect(".o_calendar_slot").toHaveCount(2);
        // FullCalendar keeps it a single event split at midnight: one segment holds the event's
        // start (Wednesday), the other its end (Thursday) - two separate events would carry both
        expect(".o_calendar_slot.fc-event-start:not(.fc-event-end)").toHaveCount(1);
        expect(".o_calendar_slot.fc-event-end:not(.fc-event-start)").toHaveCount(1);
    });

    test("subslots straddling midnight render as partials on both days", async () => {
        expect.assertions(3);
        mockTimeZone(2);
        await startEditRecurringSlots({
            aptVals: { appointment_tz: "UTC", appointment_duration: 1, slot_creation_interval: 1 },
            slotValsAll: [{ start_hour: 20.5, end_hour: 23.5 }], // appear to go over 2 days in UTC+2
        });

        // the start segment ends at midnight (Wed), the end segment begins at midnight (Thu)
        const startSeg = queryOne(".o_calendar_slot.fc-event-start");
        const endSeg = queryOne(".o_calendar_slot.fc-event-end");
        const startSubslots = queryAll(".o_calendar_subslot", { root: startSeg });
        const endSubslots = queryAll(".o_calendar_subslot", { root: endSeg });
        // the straddling slot is drawn as a partial at the bottom of Wed and the top of Thu
        expect(startSubslots).toHaveLength(2);
        expect(endSubslots).toHaveLength(2);
        expect(startSubslots.at(-1).textContent).toEqual(endSubslots.at(0).textContent);
    });
});

describe("slot editing", () => {
    test("create slots for custom appointment type", async () => {
        expect.assertions(5);
        patchWithCleanup(navigator, {
            clipboard: {
                writeText: (value) => {
                    expect(value).toBe(
                        `http://amazing.odoo.com/appointment/3?filter_staff_user_ids=%5B${userId}%5D`
                    );
                },
            },
        });
        onRpc("appointment.slot", "create", () => {
            expect.step("create slot");
        });

        await mountView({ type: "calendar", resModel: "calendar.event", arch: CALENDAR_ARCH });
        await createBookingPageFromShareMenu("Test Online Meeting");

        await clickAllDaySlot("2022-01-08");
        await animationFrame();
        expect(".o_calendar_slot").toHaveCount(1);
        expect.verifySteps(["create slot"]);

        // "Save & copy URL" both leaves edition mode and copies the url again (2nd clipboard assertion)
        await contains('button[title="Save & copy URL"]').click();
        await animationFrame();
        expect(MockServer.env["appointment.slot"]).toHaveLength(1);
    });

    test("days outside a punctual appointment's date range are greyed out", async () => {
        expect.assertions(4);
        AppointmentType._records = [
            ...AppointmentType._records,
            {
                id: 10,
                name: "Punctual Meeting",
                staff_user_ids: [userId],
                schedule_based_on: "users",
                category: "punctual",
                start_datetime: "2022-01-06 10:00:00",
                end_datetime: "2022-01-07 15:00:00",
            },
        ];

        await mountView({
            type: "calendar",
            resModel: "calendar.event",
            arch: CALENDAR_ARCH,
        });

        await editBookingPageFromSidebar("Punctual Meeting");

        // "slot selection" is the greyed out part
        // normally 1 for the "allday" grid and one for the regular one = 2
        expect('.fc-day[data-date="2022-01-05"].o_calendar_slot_selection').toHaveCount(2);
        expect('.fc-day[data-date="2022-01-06"].o_calendar_slot_selection').toHaveCount(0);
        expect('.fc-day[data-date="2022-01-07"].o_calendar_slot_selection').toHaveCount(0);
        expect('.fc-day[data-date="2022-01-08"].o_calendar_slot_selection').toHaveCount(2);
    });

    test("clicking a slot removes it while editing", async () => {
        expect.assertions(2);
        await mountView({ type: "calendar", resModel: "calendar.event", arch: CALENDAR_ARCH });
        await createBookingPageFromShareMenu("Test Online Meeting");

        await clickAllDaySlot("2022-01-08");
        await animationFrame();
        expect(".o_calendar_slot").toHaveCount(1);

        await contains(".o_calendar_slot").click();
        await animationFrame();
        expect(".o_calendar_slot").toHaveCount(0);
    });
});
