import { Component, useProps, t } from "@odoo/owl";
import { Justification } from "@l10n_it_pos/app/fiscal_printer/commands/types";

export class PrintRecSubtotalAdjustment extends Component {
    static template = "l10n_it_pos.PrintRecSubtotalAdjustment";
    props = useProps({
        operator: t.number().optional(1),
        adjustmentType: t.number(),
        description: t.string(),
        amount: t.string(),
        justification: t.selection(Object.values(Justification)).optional(Justification.LAST_20),
    });
}
