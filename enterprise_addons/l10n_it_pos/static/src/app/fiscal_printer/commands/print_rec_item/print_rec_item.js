import { Component, useProps, t } from "@odoo/owl";
import { Justification } from "@l10n_it_pos/app/fiscal_printer/commands/types";

export class PrintRecItem extends Component {
    static template = "l10n_it_pos.PrintRecItem";
    props = useProps({
        operator: t.number().optional(1),
        description: t.string(),
        quantity: t.string(),
        unitPrice: t.string(),
        department: t.or([t.string(), t.literal(false)]).optional(), // With bad configuration in backend this can be optional, adding optional to avoid errors
        justification: t.selection(Object.values(Justification)).optional(Justification.FIRST_20),
    });
}
