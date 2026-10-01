import { mailModels } from "@mail/../tests/mail_test_helpers";
import { expect, test } from "@odoo/hoot";
import { contains, defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers";

class VoipTimeConditionPeriod extends models.Model {
    _name = "voip.time.condition.period";

    all_day = fields.Boolean();
    hours_display = fields.Char();
    hours_end = fields.Float();
    hours_start = fields.Float();

    _records = [
        {
            id: 1,
            all_day: true,
            hours_display: "All day",
            hours_end: 18,
            hours_start: 9,
        },
    ];
}

defineModels({ ...mailModels, VoipTimeConditionPeriod });

test("displays all-day and time-range values after record updates", async () => {
    await mountView({
        type: "form",
        resModel: "voip.time.condition.period",
        resId: 1,
        arch: /* xml */ `
            <form>
                <field name="hours_display" widget="voip_time_condition_hours"/>
                <field name="all_day"/>
                <field name="hours_start" widget="float_time"/>
                <field name="hours_end" widget="float_time"/>
            </form>
        `,
    });

    expect("[name=hours_display]").toHaveText("All day");

    await contains("[name=all_day] input").click();
    expect("[name=hours_display]").toHaveText("9h → 18h");

    await contains("[name=hours_start] input").edit("10:30");
    await contains("[name=hours_end] input").edit("17:15");
    expect("[name=hours_display]").toHaveText("10h 30m → 17h 15m");
});
