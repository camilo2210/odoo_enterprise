import { describe, expect, test } from "@odoo/hoot";
import { mountWithCleanup, getService, mockService } from "@web/../tests/web_test_helpers";
import { animationFrame } from "@odoo/hoot-mock";
import { defineHelpdeskTimesheetModels } from "./helpdesk_timesheet_models";
import { clickOnDataset, setupChartJsForTests } from "@web/../tests/views/graph/graph_test_helpers";
import { helpdeskModels } from "@helpdesk/../tests/helpdesk_test_helpers";
import { WebClient } from "@web/webclient/webclient";


describe.current.tags("desktop");
defineHelpdeskTimesheetModels();
setupChartJsForTests();

test("Map employee_id filter to helpdesk.ticket fields", async () => {
    mockService("action", {
        doAction({ domain, res_model }) {
            if (res_model === "helpdesk.ticket") {
                expect(domain).toEqual(["|", ["user_id", "=", false], ['user_id.employee_id', '=', false]]);
            }
            return super.doAction(...arguments);
        },
    });
    helpdeskModels.HelpdeskTicketReportAnalysis._views = {
            graph: /* xml */ `
               <graph js_class="hr_timesheet_helpdesk_ticket_analysis_graph">
                    <field name="employee_id"/>
               </graph>
            `
    };
    const view = await mountWithCleanup(WebClient);
    await getService("action").doAction({
        id: 1,
        name: "tasks analysis",
        res_model: "helpdesk.ticket.report.analysis",
        type: "ir.actions.act_window",
        views: [[false, "graph"]],
        context: { group_by: ["employee_id"] },
    });
    await animationFrame();
    await clickOnDataset(view);
    await animationFrame();
    expect(`.o_list_renderer .o_data_row`).toHaveCount(3);
});
