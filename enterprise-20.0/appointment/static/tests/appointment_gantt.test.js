import { describe, expect, test } from "@odoo/hoot";
import { animationFrame, click } from "@odoo/hoot-dom";

import { mockDate } from "@odoo/hoot-mock";
import { contains, onRpc, selectGroup } from "@web/../tests/web_test_helpers";

import {
    dragPill,
    getGridContent,
    getPill,
    mountGanttView,
    SELECTORS,
} from "@web_gantt/../tests/web_gantt_test_helpers";
import { CalendarEvent, defineAppointmentModels } from "./appointment_tests_common";

describe.current.tags("desktop");

defineAppointmentModels();

/**
 * @param {string} status
 */
async function mountGanttViewWithStatus(status) {
    mockDate("2022-01-12 11:10:00", 0);

    Object.assign(CalendarEvent._records[0], {
        appointment_status: status,
        appointment_type_id: 1,
        start: "2022-01-12 10:00:00", // Late
        stop: "2022-01-12 10:30:00",
    });
    Object.assign(CalendarEvent._records[1], {
        appointment_status: status,
        appointment_type_id: 1,
        start: "2022-01-12 11:00:00", // Current
        stop: "2022-01-12 11:30:00",
    });
    Object.assign(CalendarEvent._records[2], {
        appointment_status: status,
        appointment_type_id: 1,
        start: "2022-01-12 12:00:00", // Future
        stop: "2022-01-12 12:30:00",
        partner_ids: [100, 214],
    });

    await mountGanttView({
        resModel: "calendar.event",
    });
}

function testGroupPillColorsCheckColors() {
    const almostPastEventPill = getPill("Event 1", { nth: 1 });
    const pastEventPill = getPill("Event 2", { nth: 1 });
    const futureEventPill = getPill("Event 3", { nth: 3 });

    const otherPartnerEventPills = [
        getPill("Event 1", { nth: 2 }),
        getPill("Event 2", { nth: 2 }),
        getPill("Event 3", { nth: 1 }),
        getPill("Event 3", { nth: 2 }),
        getPill("Event 3", { nth: 4 }),
    ];
    for (const pill of otherPartnerEventPills) {
        expect(pill).toHaveClass("o_appointment_booking_gantt_color_grey");
    }
    expect(almostPastEventPill).toHaveClass("o_gantt_color_4");
    expect(futureEventPill).toHaveClass("o_gantt_color_4");
    expect(pastEventPill).toHaveClass("o_gantt_color_2");
}

const STATUS_CLASSNAMES = {
    red: "o_gantt_color_1",
    orange: "o_gantt_color_2",
    lightBlue: "o_gantt_color_4",
    blue: "o_gantt_color_8",
    green: "o_gantt_color_10",
};

// minimalist version of the appointment gantt view
CalendarEvent._views.gantt = /* xml */ `
    <gantt
        js_class="appointment_booking_gantt"
        date_start="start"
        date_stop="stop"
        default_group_by="partner_ids"
        default_range="day"
        default_scale="day"
    >
        <field name="active"/>
        <field name="appointment_status"/>
        <field name="appointment_type_id"/>
        <field name="partner_id"/>
        <field name="partner_ids"/>
        <field name="resource_ids"/>
        <field name="user_id"/>
    </gantt>`;

test("empty default group gantt rendering", async () => {
    expect.assertions(19);
    mockDate("2022-01-03 08:00:00");
    CalendarEvent._records[0].appointment_type_id = 1;
    CalendarEvent._records[1].appointment_type_id = 1;
    CalendarEvent._records[2].appointment_type_id = 1;
    CalendarEvent._views.gantt = CalendarEvent._views.gantt
        .replace(`default_range="day"`, "")
        .replace(`default_scale="day"`, "");

    const partners = ["Undefined Attendees", "Partner 1", "Partner 214", "Partner 216"];
    const partnerEvents = [
        [],
        ["Event 3", "Event 1"],
        ["Event 2", "Event 3", "Event 1"],
        ["Event 2", "Event 3"],
    ];
    onRpc((args) => {
        if (
            args.model === "calendar.event" &&
            args.method === "write" &&
            args.args[0][0] === 2 &&
            "partner_ids" in args.args[1]
        ) {
            const methodArgs = args.args[1];
            expect(methodArgs.start).toBe("2022-01-21 22:00:00");
            expect(methodArgs.stop).toBe("2022-01-21 23:00:00");
            const [unlinkCommand, linkCommand] = methodArgs.partner_ids;
            expect(unlinkCommand[0]).toBe(3);
            expect(unlinkCommand[1]).toBe(214);
            expect(linkCommand[0]).toBe(4);
            expect(linkCommand[1]).toBe(100);

            expect.step("write partners and date");
        } else if (
            args.model === "calendar.event" &&
            args.method === "write" &&
            args.args[0][0] === 2 &&
            "user_id" in args.args[1]
        ) {
            expect(args.args[1].user_id).toBe(100);

            expect.step("write user id");
        } else if (args.model === "calendar.event" && args.method === "get_gantt_data") {
            expect.step("get_gantt_data");
        }
    });
    await mountGanttView({ resModel: "calendar.event" });
    const { rows } = getGridContent();
    for (let pid = 0; pid < partners.length; pid++) {
        expect(rows[pid].title).toBe(partners[pid]);
        for (let eid = 0; eid < partnerEvents[pid].length; eid++) {
            expect(rows[pid].pills[eid].title).toBe(partnerEvents[pid][eid]);
        }
    }
    const { drop } = await dragPill("Event 2", { nth: 1 });
    await drop({ row: "Partner 1", columnHeader: "21", groupHeader: "January 2022", part: 2 });
    await expect.waitForSteps([
        "get_gantt_data",
        "write partners and date",
        "write user id",
        "get_gantt_data",
    ]);
});

test("'Add Closing Day' button rendering - 1", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "appointment.group_appointment_manager") {
            return true;
        }
    });
    await mountGanttView({
        resModel: "calendar.event",
    });
    expect(".o_appointment_booking_gantt_button_add_leaves").toHaveCount(1, {
        message: "the button should have been rendered",
    });
});

test("'Add Closing Day' button rendering - 2", async () => {
    onRpc("has_group", ({ args }) => {
        if (args[1] === "appointment.group_appointment_manager") {
            return false;
        }
    });
    await mountGanttView({
        resModel: "calendar.event",
    });
    expect(".o_appointment_booking_gantt_button_add_leaves").toHaveCount(0, {
        message: "the button should not have been rendered: the user is not an appointment manager",
    });
});

test("group pill colors", async () => {
    mockDate("2022-01-12 11:00:00", 0);
    Object.assign(CalendarEvent._records[0], {
        appointment_type_id: 1,
        start: "2022-01-12 11:16:00",
        stop: "2022-01-12 12:00:00",
    });
    Object.assign(CalendarEvent._records[1], {
        appointment_type_id: 1,
        start: "2022-01-12 10:30:00",
        stop: "2022-01-12 12:00:00",
    });
    Object.assign(CalendarEvent._records[2], {
        appointment_type_id: 1,
        start: "2022-01-12 12:00:00",
        stop: "2022-01-12 13:00:00",
    });
    await mountGanttView({
        resModel: "calendar.event",
    });
    testGroupPillColorsCheckColors();
    await click(SELECTORS.sparse);
    await animationFrame();
    testGroupPillColorsCheckColors();
    await selectGroup("appointment_type_id");
    // when not grouping by attendees we show "lateness" every time
    expect(document.querySelectorAll(".o_appointment_booking_gantt_color_grey")).toBeEmpty();
    await selectGroup("partner_ids");
    testGroupPillColorsCheckColors();
    await click(SELECTORS.dense);
    await animationFrame();
    testGroupPillColorsCheckColors();
});

test("appointment status pill colors: request", async () => {
    await mountGanttViewWithStatus("request");

    expect(getPill("Event 1", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.orange);
    expect(getPill("Event 2", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.orange);
    expect(getPill("Event 3", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.blue);

    expect(getPill("Event 1", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 2", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 3", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
});

test("appointment status pill colors: booked", async () => {
    await mountGanttViewWithStatus("booked");

    expect(getPill("Event 1", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.orange);
    expect(getPill("Event 2", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.lightBlue);
    expect(getPill("Event 3", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.lightBlue);

    expect(getPill("Event 1", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 2", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 3", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
});

test("appointment status pill colors: attended", async () => {
    await mountGanttViewWithStatus("attended");

    expect(getPill("Event 1", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.green);
    expect(getPill("Event 2", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.green);
    expect(getPill("Event 3", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.green);

    expect(getPill("Event 1", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 2", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 3", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
});

test("appointment status pill colors: no_show", async () => {
    await mountGanttViewWithStatus("no_show");

    expect(getPill("Event 1", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.red);
    expect(getPill("Event 2", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.red);
    expect(getPill("Event 3", { nth: 1 })).toHaveClass(STATUS_CLASSNAMES.red);

    expect(getPill("Event 1", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 2", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
    expect(getPill("Event 3", { nth: 2 })).toHaveClass("o_appointment_booking_gantt_color_grey");
});

test("undo action: move and undo a pill", async () => {
    expect.assertions(4);
    mockDate("2022-01-03 08:00:00")
    CalendarEvent._views.gantt = CalendarEvent._views.gantt
        .replace(`default_range="day"`, "")
        .replace(`default_scale="day"`, "");

    onRpc("gantt_undo_drag_drop", function ({ model, args }) {
        expect(args[0]).toEqual(2);
        expect(args[1]).toEqual("reschedule");
        expect(args[2]).toEqual({
                partner_ids: [ 214, 216 ],
                start: "2022-01-05 10:00:00",
                stop: "2022-01-05 11:00:00",
            },
        );
        return this.env[model].write([args[0]], args[2]);
    });

    await mountGanttView({ resModel: "calendar.event" });

    const { drop } = await dragPill("Event 2", { nth: 1 });
    await drop({ row: "Partner 1", columnHeader: "21", groupHeader: "January 2022", part: 2 });

    await contains(".o_notification_buttons button i[title='Undo']").click();
    expect(".o_notification_content").toHaveText("Record reschedule undone");
});
