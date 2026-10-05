import { Component, t, useProps } from "@odoo/owl";

import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class PayrunNewDropdown extends Component {
    static template = "hr_payroll.PayrunNewDropdown";
    static components = {
        Dropdown,
        DropdownItem,
    };

    props = useProps({
        onCreatePayslip: t.function(),
        onCreatePayRun: t.function(),
    });
}
