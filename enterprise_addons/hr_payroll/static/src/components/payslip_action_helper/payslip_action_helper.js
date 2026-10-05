import { Component, t, useProps } from "@odoo/owl";

export class PayslipActionHelper extends Component {
    static template = "hr_payroll.PayslipActionHelper";

    props = useProps({
        payrunId: t.number().optional(),
        onClickCreate: t.function(),
    });
}
