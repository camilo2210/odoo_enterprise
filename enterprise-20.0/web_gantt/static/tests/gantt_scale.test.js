import { beforeEach, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import { defineGanttModels } from "./gantt_mock_models";
import { contains } from "@web/../tests/web_test_helpers";
import { mountGanttView } from "./web_gantt_test_helpers";

defineGanttModels();

beforeEach(() => {
    mockDate("2026-02-01 00:00:00");
});

test("custom scale selector updates UI immediately before clicking apply", async () => {
    await mountGanttView({
        resModel: "tasks",
        arch: `<gantt date_start="start" date_stop="stop" />`,
    });

    await contains(".scale_button_selection").click();

    const startPicker = ".o_gantt_picker:first-of-type";
    const stopPicker = ".o_gantt_picker:last-of-type";

    expect(startPicker).not.toHaveText(/17/);
    expect(stopPicker).not.toHaveText(/18/);

    await contains(startPicker).click();
    await contains(".o_date_item_cell:contains(17)").click();

    expect(startPicker).toHaveText(/17/);

    await contains(stopPicker).click();
    await contains(".o_date_item_cell:contains(18)").click();

    expect(stopPicker).toHaveText(/18/);

    await contains(".o_gantt_scale_selector_menu .btn-primary:contains(Apply)").click();

    const rangeToggle = ".scale_button_selection";
    expect(rangeToggle).toHaveText(/17/);
    expect(rangeToggle).toHaveText(/18/);
});
