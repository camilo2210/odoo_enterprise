import { Component, t, useProps } from "@odoo/owl";

export class HrTaxBreakupPopover extends Component {
    static template = "l10n_in_hr_payroll.hr_tax_breakup_popover";
    props = useProps({
        taxBreakup: t.object(),
        totalTax: t.string(),
        close: t.function(),
    });
}
