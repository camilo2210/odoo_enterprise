import { Component, useProps, t } from "@odoo/owl";
import { Justification } from "@l10n_it_pos/app/fiscal_printer/commands/types";

export class PrintRecRefund extends Component {
    static template = "l10n_it_pos.PrintRecRefund";
    props = useProps({
        operator: t.number().optional(1),
        description: t.string(),
        quantity: t.string(),
        unitPrice: t.string(),
        department: t.string(),
        justification: t.selection(Object.values(Justification)).optional(Justification.FIRST_20),
    });
}
