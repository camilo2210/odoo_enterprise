import { animationFrame, beforeEach, describe, expect, test } from "@odoo/hoot";
import { mockDate } from "@odoo/hoot-mock";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    mockService,
    toggleMenuItem,
    toggleSearchBarMenu,
} from "@web/../tests/web_test_helpers";
import { defineHrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers";
import { HrPayslip } from "@hr_payroll/../tests/mock_server/mock_models/hr_payslip";

class TestW2Form extends models.Model {
    _name = "test.w2.form";
    payslip_ids = fields.Many2many({ relation: "hr.payslip", string: "Payslips" });
    _records = [{ id: 1, payslip_ids: [] }];
}

describe.current.tags("desktop");
defineHrPayrollModels();
defineModels([TestW2Form]);

beforeEach(() => {
    mockDate("2025-01-01 12:00:00", +0);
    HrPayslip._records = [];
});

test("Test header buttons of payslip list view filtered by payrun", async () => {
    await mountView({
        type: "list",
        resModel: "hr.payslip",
        context: {
            search_default_payslip_run_id: 1,
        },
    });
    await animationFrame();
    expect(".o_control_panel_main_buttons button").toHaveCount(1);
    expect(".o_list_button_add").toHaveText("New");
});

test('Clicking "Create a Payslip" from empty helper opens payslip form', async () => {
    mockService("action", {
        doAction: async (action) => {
            expect.step(action);
        },
    });

    await mountView({
        type: "form",
        resModel: "test.w2.form",
        resId: 1,
        arch: `
            <form>
                <field name="payslip_ids">
                    <list create="false">
                        <field name="employee_id"/>
                    </list>
                </field>
            </form>
        `,
    });
    await contains(".o_field_x2many_list_row_add button").click();
    expect(".o_view_nocontent").toHaveText(/Create a Payslip/);
    await contains('a:contains("Create a Payslip")').click();
    expect.verifySteps(["hr_payroll.action_hr_payslip_new"]);
});

test("Filtering on payslip_run_id = False (Off-Cycle) with no results renders the empty helper", async () => {
    await mountView({
        type: "list",
        resModel: "hr.payslip",
        noContentHelp: "<p>Create a Payslip</p>",
        arch: `
            <list js_class="hr_payroll_payslip_list">
                <field name="id"/>
                <field name="employee_id"/>
            </list>
        `,
        searchViewArch: `
            <search>
                <field name="payslip_run_id"/>
                <filter string="Off-Cycle" name="filter_off_cycle" domain="[('payslip_run_id', '=', False)]"/>
            </search>
        `,
    });
    await animationFrame();
    expect(".o_view_nocontent").toHaveCount(1);

    await toggleSearchBarMenu();
    await toggleMenuItem("Off-Cycle");
    await animationFrame();

    expect(".o_view_nocontent").toHaveCount(1);
    expect(".o_view_nocontent").toHaveText(/No Payslips/);
});
