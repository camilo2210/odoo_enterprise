import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

import {
    click,
    contains,
    openView,
    registerArchs,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";

import { expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";

setupVoipTests();

const arch = {
    "voip.call,false,calendar": /*xml*/ `
    <calendar js_class="voip_call_calendar" date_start="effective_start_date" date_stop="end_date" mode="week" event_open_popup="true" create="False" color="user_id">
        <field name="direction" invisible="True"/>
        <field name="phone_number" invisible="True"/>
        <field name="create_date" invisible="True"/>
        <field name="duration" invisible="True"/>
        <field name="partner_id" invisible="not partner_id" widget="voip_calendar_many2one" options="{'noLabel': True}"/>
        <field name="user_id" filters="True" invisible="True"/>
        <field name="state" string="Status" filters="True" invisible="True"/>
    </calendar>
    `,
};

test("call calendar view displays calls correctly", async () => {
    await mockDate("2000-09-10 08:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    await registerArchs(arch);
    await start();
    const partnerId_1 = pyEnv["res.partner"].create({ name: "Contact 1", phone: "+1234567890" });
    pyEnv["voip.call"].create([
        {
            create_date: "2000-09-10 14:00:00",
            partner_id: partnerId_1,
            phone_number: "+1234567890",
        },
        {
            create_date: "2000-09-11 10:00:00",
            start_date: "2000-09-11 10:00:00",
            duration: 6300, // 1h45min
            phone_number: "+9876543210",
        },
    ]);
    await openView({ res_model: "voip.call", views: [[false, "calendar"]] });
    expect(`.o_calendar_renderer`).toHaveCount(1);
    expect(`.o_event`).toHaveCount(2); // 2 calls created
});

test("call calendar view displays correct title on the calendar grid", async () => {
    await mockDate("2000-09-10 08:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    registerArchs(arch);
    await start();
    const partnerId = pyEnv["res.partner"].create({ name: "Contact 1", phone: "+1234567890" });
    const [call_with_partner, call_with_no_partner] = pyEnv["voip.call"].create([
        {
            start_date: "2000-09-10 14:00:00",
            duration: 1200, // 20 minutes
            partner_id: partnerId,
            phone_number: "+1234567890",
            direction: "incoming",
        },
        {
            start_date: "2000-09-12 10:00:00",
            duration: 14400, // 4 hours
            phone_number: "+1234567890",
            direction: "outgoing",
        },
    ]);
    await openView({ res_model: "voip.call", views: [[false, "calendar"]] });
    expect(`a[data-event-id='${call_with_partner}'] .o_event_title i`).toHaveAttribute(
        "data-icon",
        "south_west"
    );
    expect(`a[data-event-id='${call_with_partner}'] .o_event_title`).toHaveText("Contact 1, 14:00");
    expect(`a[data-event-id='${call_with_no_partner}'] .o_event_title i`).toHaveAttribute(
        "data-icon",
        "north_east"
    );
    expect(`a[data-event-id='${call_with_no_partner}'] .o_event_title`).toHaveText(
        "+1234567890, 10:00"
    );
});

test("call calendar view displays calls date and duration including the day of the week with end date", async () => {
    await mockDate("2000-09-10 08:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    registerArchs(arch);
    await start();
    pyEnv["voip.call"].create({
        start_date: "2000-09-10 14:00:00",
        duration: 1200, // 20 minutes
        phone_number: "+1234567890",
    });
    await openView({ res_model: "voip.call", views: [[false, "calendar"]] });
    await click("a[data-event-id='1']");
    await contains(".o_popover_body", { count: 1 });
    expect(document.querySelector(".o_popover_body").textContent.replace(/\s/g, " ").trim()).toBe(
        "Sunday, September 10, 2000 • 14:00 – 14:20 (20 minutes)"
    );
});

test("call calendar view displays calls create_date and no duration when there is no end date", async () => {
    await mockDate("2000-09-10 08:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    registerArchs(arch);
    await start();
    pyEnv["voip.call"].create({
        create_date: "2000-09-13 10:55:00",
        phone_number: "+9876543210",
        state: "rejected",
    });
    await openView({ res_model: "voip.call", views: [[false, "calendar"]] });
    await click("a[data-event-id='1']");
    await contains(".o_popover_body", { count: 1 });
    expect(document.querySelector(".o_popover_body").textContent.replace(/\s/g, " ").trim()).toBe(
        "Wednesday, September 13, 2000 • 10:55"
    );
});
