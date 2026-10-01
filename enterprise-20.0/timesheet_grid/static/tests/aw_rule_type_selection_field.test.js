import { describe, expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { contains, editSelectMenu, mountView } from "@web/../tests/web_test_helpers";
import { defineTimesheetModels } from "@hr_timesheet/../tests/hr_timesheet_models";

describe.current.tags("desktop");

defineTimesheetModels();

test("aw_rule_type_selection: renders correctly in edit mode and handles empty state", async () => {
    await mountView({
        type: "form",
        resModel: "aw.rule",
        arch: `<form><field name="type" widget="aw_rule_type_selection"/></form>`,
    });

    expect(".o_field_widget[name='type'] i.oi-fw").toHaveCount(0);

    await contains(".o_field_widget[name='type'] input").click();
    expect(queryAll(".o_select_menu-choices i.oi-fw").length).toBe(10);

    await editSelectMenu(".o_field_widget[name='type'] input", { value: "development" });
    expect(".o_field_widget[name='type'] i[data-icon='code']").toHaveCount(1);
});

test("aw_rule_type_selection: renders correctly in readonly mode", async () => {
    await mountView({
        type: "form",
        resModel: "aw.rule",
        resId: 1,
        arch: `<form edit="0"><field name="type" widget="aw_rule_type_selection"/></form>`,
    });

    expect(".o_field_widget[name='type'] span").toHaveText("Development");
    expect(".o_field_widget[name='type'] i[data-icon='code']").toHaveCount(1);
});

test("aw_rule_type_selection: renders correctly in a list view", async () => {
    await mountView({
        type: "list",
        resModel: "aw.rule",
        arch: `<list><field name="name" /><field name="type" widget="aw_rule_type_selection"/></list>`,
    });

    expect(".o_data_row:eq(1) .o_data_cell[name='type']").toHaveText("Meeting");
    expect(".o_data_row:eq(1) .o_data_cell[name='type'] i[data-icon='calendar_today']").toHaveCount(
        1
    );
});
