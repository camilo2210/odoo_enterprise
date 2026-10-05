import { describe, expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { mockDate } from "@odoo/hoot-mock";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { defineModels } from "@web/../tests/web_test_helpers";
import { SELECTORS } from "@web_gantt/../tests/web_gantt_test_helpers";
import {
    Attendances,
    Employees,
    mountGanttViewWithProgressBars,
} from "@hr_attendance_gantt/../tests/attendance_gantt_test_helpers";

describe.current.tags("desktop");

defineModels([Attendances, Employees]);
defineMailModels();

test("Empty attendance-based employees are shown in yellow", async () => {
    mockDate("2018-12-10 16:00:00", +0);
    await mountGanttViewWithProgressBars({
        1: { value: 0, max_value: 8, attendance_based: true },
        2: { value: 0, max_value: 8, attendance_based: false },
    });

    // both empty employees still have their progress bar shown
    expect(SELECTORS.progressBar).toHaveCount(2);

    const [pb1, pb2] = queryAll(SELECTORS.progressBar);
    // attendance-based empty employee is colored in yellow (warning)
    expect(pb1.querySelector("span")).toHaveClass("bg-warning");
    // non attendance-based empty employee is not colored
    expect(pb2.querySelector("span")).not.toHaveClass("bg-warning");

    // same thing for their labels
    const [label1, label2] = queryAll(SELECTORS.progressBarForeground);
    expect(label1).toHaveClass("text-warning");
    expect(label2).not.toHaveClass("text-warning");
});

test("Attendance-based employee with attendances is not shown in yellow", async () => {
    mockDate("2018-12-10 16:00:00", +0);
    await mountGanttViewWithProgressBars({
        1: { value: 4, max_value: 8, attendance_based: true },
    });

    // progress bar should not be in yellow
    expect(SELECTORS.progressBar).toHaveCount(1);
    const [pb1] = queryAll(SELECTORS.progressBar);
    expect(pb1.querySelector("span")).not.toHaveClass("bg-warning");

    // same for the progress bar label
    const [label1] = queryAll(SELECTORS.progressBarForeground);
    expect(label1).not.toHaveClass("text-warning");
});
