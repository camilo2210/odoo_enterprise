import { openListView, start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Display of outgoing status label", async () => {
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        direction: "outgoing",
        state: "terminated",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name='id'/>
                <field name="state" string="Status" widget="voip_call_status_badge"/>
                <field name="direction" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_row").toHaveCount(1);
    expect(`.o_data_cell[name="id"]`).toHaveText("1");
    expect(`.o_data_cell[name="state"]`).toHaveText("Completed");
    expect(`.o_data_cell[name="state"] .badge`).toHaveAttribute(
        "title",
        "The call ended successfully."
    );
});

test("Display of incoming status label", async () => {
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        direction: "incoming",
        state: "terminated",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name='id'/>
                <field name="state" string="Status" widget="voip_call_status_badge"/>
                <field name="direction" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_row").toHaveCount(1);
    expect(`.o_data_cell[name="id"]`).toHaveText("1");
    expect(`.o_data_cell[name="state"]`).toHaveText("Completed");
});

test("Display of fresh live status label without local session", async () => {
    mockDate("2026-01-01 10:00:00");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2026-01-01 09:58:00",
        direction: "incoming",
        state: "calling",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name='id'/>
                <field name="state" string="Status" widget="voip_call_status_badge"/>
                <field name="create_date" column_invisible="True"/>
                <field name="direction" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_row").toHaveCount(1);
    expect(`.o_data_cell[name="id"]`).toHaveText("1");
    expect(`.o_data_cell[name="state"]`).toHaveText("Ringing");
    expect(`.o_data_cell[name="state"] .badge`).toHaveAttribute(
        "title",
        "The callee's phone is ringing right now."
    );
});

test("Display of fresh ongoing status label without local session", async () => {
    mockDate("2026-01-01 10:00:00");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2026-01-01 08:00:00",
        direction: "outgoing",
        start_date: "2026-01-01 08:01:00",
        state: "ongoing",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name='id'/>
                <field name="state" string="Status" widget="voip_call_status_badge"/>
                <field name="create_date" column_invisible="True"/>
                <field name="direction" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_row").toHaveCount(1);
    expect(`.o_data_cell[name="id"]`).toHaveText("1");
    expect(`.o_data_cell[name="state"]`).toHaveText("Ongoing");
    expect(`.o_data_cell[name="state"] .badge`).toHaveAttribute(
        "title",
        "Both parties are in the call right now."
    );
});

test("Display of stale ongoing status label without local session", async () => {
    mockDate("2026-01-01 10:00:00");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2026-01-01 05:59:59",
        direction: "outgoing",
        state: "ongoing",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name='id'/>
                <field name="state" string="Status" widget="voip_call_status_badge"/>
                <field name="create_date" column_invisible="True"/>
                <field name="direction" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_row").toHaveCount(1);
    expect(`.o_data_cell[name="id"]`).toHaveText("1");
    expect(`.o_data_cell[name="state"]`).toHaveText("Ended Unexpectedly");
    expect(`.o_data_cell[name="state"] .badge`).toHaveAttribute(
        "title",
        "Call ended for another reason than a hangup."
    );
});

for (const { direction, state, label, tooltip } of [
    {
        direction: "outgoing",
        state: "aborted",
        label: "Aborted",
        tooltip: "The caller ended the call before pickup.",
    },
    {
        direction: "incoming",
        state: "completed_elsewhere",
        label: "Completed Elsewhere",
        tooltip: "The call was answered on another device.",
    },
    {
        direction: "incoming",
        state: "missed",
        label: "Missed",
        tooltip: "The callee did not pick up.",
    },
    {
        direction: "outgoing",
        state: "rejected",
        label: "Rejected",
        tooltip: "The callee pressed the hangup key while ringing.",
    },
]) {
    test(`Display of ${state} status label and tooltip`, async () => {
        const pyEnv = await startServer();
        pyEnv["voip.call"].create({ direction, state });
        await start();
        await openListView("voip.call", {
            arch: `
                <list>
                    <field name="state" string="Status" widget="voip_call_status_badge"/>
                    <field name="direction" column_invisible="True"/>
                </list>
            `,
        });

        expect(`.o_data_cell[name="state"]`).toHaveText(label);
        expect(`.o_data_cell[name="state"] .badge`).toHaveAttribute("title", tooltip);
    });
}
