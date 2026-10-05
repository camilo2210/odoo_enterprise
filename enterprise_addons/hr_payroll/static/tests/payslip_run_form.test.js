import { expect, test, describe } from "@odoo/hoot";
import { click, queryFirst } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import {
    mountViewInDialog,
    contains,
    mockService,
    onRpc,
    selectFieldDropdownItem,
} from "@web/../tests/web_test_helpers";
import { defineHrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers";

defineHrPayrollModels();
describe.current.tags("desktop");

test("Pay Run wizard validates on Continue click and shows errors for missing required fields", async () => {
    mockService("action", {
        doAction(action) {
            expect.step("doAction called");
            return true;
        },
    });
    onRpc("hr.payslip.run", "action_payroll_hr_version_list_view_payrun", () => {
        expect.step("action_payroll_hr_version_list_view_payrun called");
        return {
            type: "ir.actions.act_window",
            name: "Select Employees",
            res_model: "hr.version",
            view_mode: "list",
            help: "<p>No records</p>",
        };
    });
    await mountViewInDialog({
        type: "form",
        resModel: "hr.payslip.run",
        context: { dialog_size: "medium" },
        arch: `
            <form string="Pay Runs" js_class="hr_payslip_batch_form">
                <sheet>
                    <group>
                        <field name="company_id"/>
                        <field name="date_start"/>
                        <field name="date_end"/>
                    </group>
                </sheet>
            </form>
        `,
    });
    const continueButton = queryFirst(".btn-primary");
    await click(continueButton);
    await animationFrame();
    // company_id fails, date_start and date_end are precomputed
    expect("label.o_field_invalid").toHaveCount(1);

    await selectFieldDropdownItem("company_id", "Hermit");
    await contains("[name='date_start'] input").edit("2025-01-01");
    await contains("[name='date_end'] input").edit("2025-01-31");
    await animationFrame();
    await click(continueButton);
    await animationFrame();

    expect.verifySteps([
        "action_payroll_hr_version_list_view_payrun called",
        "doAction called",
    ]);
});
