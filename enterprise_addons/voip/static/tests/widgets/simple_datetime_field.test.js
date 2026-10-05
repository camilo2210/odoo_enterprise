import { openListView, start, startServer } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";

describe.current.tags("desktop");
setupVoipTests();

test("Today with duration_field shows date plus duration in parentheses", async () => {
    mockDate("2026-01-01 10:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2026-01-01 09:58:00",
        duration: 330,
        duration_human_readable: "5m 30s",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name="create_date" widget="voip_simple_datetime" options="{'duration_field': 'duration_human_readable'}"/>
                <field name="duration_human_readable" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_cell[name='create_date']").toHaveText("Today, 9:58 AM (5m 30s)");
});

test("Yesterday with duration_field", async () => {
    mockDate("2026-01-01 10:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2025-12-31 22:15:00",
        duration_human_readable: "1m 10s",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name="create_date" widget="voip_simple_datetime" options="{'duration_field': 'duration_human_readable'}"/>
                <field name="duration_human_readable" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_cell[name='create_date']").toHaveText("Yesterday, 10:15 PM (1m 10s)");
});

test("Historical date with duration_field", async () => {
    mockDate("2026-01-01 10:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2025-12-20 15:30:00",
        duration_human_readable: "0s",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name="create_date" widget="voip_simple_datetime" options="{'duration_field': 'duration_human_readable'}"/>
                <field name="duration_human_readable" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_cell[name='create_date']").toHaveText("12/20/25, 3:30 PM (0s)");
});

test("Without duration value shows only date", async () => {
    mockDate("2026-01-01 10:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2026-01-01 09:58:00",
        duration_human_readable: false,
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name="create_date" widget="voip_simple_datetime" options="{'duration_field': 'duration_human_readable'}"/>
                <field name="duration_human_readable" column_invisible="True"/>
            </list>
        `,
    });
    expect(".o_data_cell[name='create_date']").toHaveText("Today, 9:58 AM");
});

test("Without duration_field option shows only date", async () => {
    mockDate("2026-01-01 10:00:00", "Etc/UTC");
    const pyEnv = await startServer();
    pyEnv["voip.call"].create({
        create_date: "2026-01-01 09:58:00",
        duration_human_readable: "5m 30s",
    });
    await start();
    await openListView("voip.call", {
        arch: `
            <list>
                <field name="create_date" widget="voip_simple_datetime"/>
            </list>
        `,
    });
    expect(".o_data_cell[name='create_date']").toHaveText("Today, 9:58 AM");
});
