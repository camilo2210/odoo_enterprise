import { Component, props, t } from "@odoo/owl";
import { useSubEnv } from "@web/owl2/utils";
import { useService } from "@web/core/utils/hooks";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { PayRunButtonBox } from "../button_box/payrun_button_box";
import { PayRunViewButton } from "@hr_payroll/views/payslip_run_view_button/payrun_view_button";

export class PayRunDetailsSheet extends Component {
    static template = "hr_payroll.PayRunDetailsSheet";
    static components = {
        ...KanbanRecord.components,
        PayRunButtonBox,
        ViewButton: PayRunViewButton,
    };

    props = props({
        close: t.function().optional(),
    });

    setup() {
        this.payRunDetails = useService("payRunDetails");
        useSubEnv({
            isPayRunReady: this.payRunDetails.state.isPayRunReady ?? Promise.resolve(),
            onClickViewButton: (params) => {
                const executed = this.payRunDetails.state.onClickViewButton?.(params);
                this.payRunDetails.close();
                return executed;
            },
        });
    }

    get state() {
        return this.payRunDetails.state;
    }
}
