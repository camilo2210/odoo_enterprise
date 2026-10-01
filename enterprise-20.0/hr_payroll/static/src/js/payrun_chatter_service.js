import { Plugin, signal } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { services } from "@web/core/services";

export class PayRunChatterService extends Plugin {
    visible = signal(
        JSON.parse(browser.sessionStorage.getItem("isPayRunChatterOpened")) ?? false
    );
    payslipRun = signal(undefined);

    toggleChatter() {
        this.visible.set(!this.visible());
        browser.sessionStorage.setItem("isPayRunChatterOpened", this.visible());
    }

    closeChatter() {
        this.visible.set(false);
        browser.sessionStorage.setItem("isPayRunChatterOpened", false);
    }

    selectPayslipRun(record) {
        this.payslipRun.set(record);
    }

    get payslipRunId() {
        return this.payslipRun()?.resId;
    }

    get chatterProps() {
        return {
            threadId: this.payslipRunId,
            threadModel: "hr.payslip.run",
            isChatterAside: true,
            hasParentReloadOnActivityChanged: true,
            hasParentReloadOnAttachmentsChanged: true,
        };
    }
}

services.add(PayRunChatterService);

