import { describe, test, expect } from "@odoo/hoot";
import {
    getService,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";
import { defineTimesheetModels } from "./hr_timesheet_models";

describe.current.tags("desktop");
defineTimesheetModels();

test("Frequency Viewer can be opened", async () => {
    localStorage.setItem("aw_timesheet_frequency", JSON.stringify({
        "Activity 1": {
            '{"project_id":1,"task_id":1}': 5,
        }
    }));

    onRpc("project.project", "read", (args) => {
        return [{ id: 1, display_name: "Project 1" }];
    });
    onRpc("project.task", "read", (args) => {
        return [{ id: 1, display_name: "Task 1" }];
    });

    await mountWithCleanup(WebClient);
    await getService("action").doAction({
        type: "ir.actions.client",
        tag: "frequency_viewer",
    });

    expect(".o_list_renderer").toHaveCount(1);
    expect(".o_data_row").toHaveCount(1);
    expect(".o_data_cell:contains('Activity 1')").toHaveCount(1);
    expect(".o_data_cell:contains('Project 1')").toHaveCount(1);
    expect(".o_data_cell:contains('Task 1')").toHaveCount(1);
});
