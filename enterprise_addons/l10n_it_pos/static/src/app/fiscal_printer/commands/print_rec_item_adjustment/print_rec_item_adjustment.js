import { Component, useProps, t } from "@odoo/owl";
import { Justification } from "@l10n_it_pos/app/fiscal_printer/commands/types";

export class PrintRecItemAdjustment extends Component {
    static template = "l10n_it_pos.PrintRecItemAdjustment";
    props = useProps({
        operator: t.number().optional(1),
        adjustmentType: t.number(),
        description: t.string(),
        department: t.or([t.string(), t.literal(false)]),
        amount: t.string(),
        justification: t.selection(Object.values(Justification)).optional(Justification.FIRST_20),
    });
}
