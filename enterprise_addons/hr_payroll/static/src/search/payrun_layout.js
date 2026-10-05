import { usePlugin, useEffect, proxy } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { PayRunChatterService } from "@hr_payroll/js/payrun_chatter_service";
import { PayRunControlPanel } from "@hr_payroll/search/payrun_control_panel";
import { Chatter } from "@mail/chatter/web_portal_project/chatter";

export class PayRunLayout extends Layout {
    static template = "hr_payroll.PayRunLayout";
    static components = {
        ...Layout.components,
        Chatter,
        PayRunControlPanel,
    };

    setup() {
        super.setup();
        this.components = { ...this.components, ControlPanel: PayRunControlPanel };
        this.uiService = useService("ui");
        this.payRunChatter = usePlugin(PayRunChatterService);

        this.state = proxy({ payRunReactive: this.env.payRunReactive });
        useEffect(() => {
            const payRunId = this.state.payRunReactive?.payRunId
            if (payRunId) {
                this.payRunChatter.selectPayslipRun({ resId: payRunId });
            } else {
                this.payRunChatter.closeChatter();
            }
        });
    }
}
