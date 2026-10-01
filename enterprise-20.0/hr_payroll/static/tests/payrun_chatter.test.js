import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { browser } from "@web/core/browser/browser";
import { contains, mountView } from "@web/../tests/web_test_helpers";
import { defineHrPayrollModels } from "@hr_payroll/../tests/hr_payroll_test_helpers";
import { PayRunChatterService } from "@hr_payroll/js/payrun_chatter_service";

describe.current.tags("desktop");
defineHrPayrollModels();

describe("PayRunChatterService", () => {
    let service;

    beforeEach(() => {
        service = new PayRunChatterService({});
    });

    test("toggleChatter flips visibility and writes to sessionStorage", () => {
        service.toggleChatter();
        expect(service.visible()).toBe(true);
        expect(JSON.parse(browser.sessionStorage.getItem("isPayRunChatterOpened"))).toBe(true);

        service.toggleChatter();
        expect(service.visible()).toBe(false);
        expect(JSON.parse(browser.sessionStorage.getItem("isPayRunChatterOpened"))).toBe(false);
    });

    test("closeChatter forces visible to false and persists", () => {
        service.toggleChatter();
        expect(service.visible()).toBe(true);

        service.closeChatter();
        expect(service.visible()).toBe(false);
        expect(JSON.parse(browser.sessionStorage.getItem("isPayRunChatterOpened"))).toBe(false);
    });

    test("selectPayslipRun exposes payslipRunId", () => {
        const fakeRecord = { resId: 42 };
        service.selectPayslipRun(fakeRecord);
        expect(service.payslipRun()).toEqual(fakeRecord);
        expect(service.payslipRunId).toBe(42);
    });

    test("payslipRunId is undefined when nothing is selected", () => {
        expect(service.payslipRunId).toBe(undefined);
    });

    test("selectPayslipRun(null) clears the selection", () => {
        service.selectPayslipRun({ resId: 99 });
        expect(service.payslipRunId).toBe(99);

        service.selectPayslipRun(null);
        expect(service.payslipRunId).toBe(undefined);
    });
});

describe("PayrunKanbanRecord - toggleChatter state transitions", () => {
    let service;

    beforeEach(() => {
        service = new PayRunChatterService({});
    });

    function makeToggle(resId) {
        const record = { resId };
        return function toggle() {
            if (service.visible()) {
                if (service.payslipRunId === resId) {
                    service.selectPayslipRun(null);
                    service.toggleChatter();
                } else {
                    service.selectPayslipRun(record);
                }
                return;
            }
            service.selectPayslipRun(record);
            service.toggleChatter();
        };
    }

    test("clicking a card while chatter is closed opens it and selects the card", () => {
        const toggleA = makeToggle(1);
        toggleA();
        expect(service.visible()).toBe(true);
        expect(service.payslipRunId).toBe(1);
    });

    test("clicking the same selected card while chatter is open closes it and deselects", () => {
        const toggleA = makeToggle(1);
        toggleA();
        toggleA();
        expect(service.visible()).toBe(false);
        expect(service.payslipRunId).toBe(undefined);
    });

    test("clicking a different card while chatter is open switches selection without closing", () => {
        const toggleA = makeToggle(1);
        const toggleB = makeToggle(2);

        toggleA();
        expect(service.payslipRunId).toBe(1);

        toggleB();
        expect(service.visible()).toBe(true);
        expect(service.payslipRunId).toBe(2);
    });

    test("independent toggle sequences on two cards do not interfere", () => {
        const toggleA = makeToggle(1);
        const toggleB = makeToggle(2);

        toggleA();
        toggleB();
        toggleB();
        expect(service.visible()).toBe(false);
        expect(service.payslipRunId).toBe(undefined);
    });
});

describe("PayRunControlPanel - chatter toggle button", () => {
    test("chatter button is rendered in the control panel", async () => {
        await mountView({
            type: "list",
            resModel: "hr.payslip",
            context: { search_default_payslip_run_id: 1 },
        });
        await animationFrame();
        expect("button[data-tooltip='Chatter']").toHaveCount(1);
    });

    test("chatter button initially shows forum icon (chatter closed)", async () => {
        await mountView({
            type: "list",
            resModel: "hr.payslip",
            context: { search_default_payslip_run_id: 1 },
        });
        await animationFrame();
        expect("button[data-tooltip='Chatter'] [data-icon='forum']").toHaveCount(1);
        expect("button[data-tooltip='Chatter']").not.toHaveClass("active");
    });

    test("clicking chatter button opens the chatter (icon switches to 'close')", async () => {
        await mountView({
            type: "list",
            resModel: "hr.payslip",
            context: { search_default_payslip_run_id: 1 },
        });
        await animationFrame();

        await contains("button[data-tooltip='Chatter']").click();
        await animationFrame();
        expect("button[data-tooltip='Chatter']").toHaveClass("active");
        expect("button[data-tooltip='Chatter'] [data-icon='close']").toHaveCount(1);
    });

    test("clicking chatter button twice closes the chatter again", async () => {
        await mountView({
            type: "list",
            resModel: "hr.payslip",
            context: { search_default_payslip_run_id: 1 },
        });
        await animationFrame();

        await contains("button[data-tooltip='Chatter']").click();
        await animationFrame();
        await contains("button[data-tooltip='Chatter']").click();
        await animationFrame();
        expect("button[data-tooltip='Chatter']").not.toHaveClass("active");
        expect("button[data-tooltip='Chatter'] [data-icon='forum']").toHaveCount(1);
    });
});
