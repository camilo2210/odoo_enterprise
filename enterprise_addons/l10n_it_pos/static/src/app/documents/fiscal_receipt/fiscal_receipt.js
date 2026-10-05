import { Component, useProps, t } from "@odoo/owl";
import { Header, Body, Footer } from "@l10n_it_pos/app/documents/fiscal_document";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

export class FiscalReceipt extends Component {
    static template = "l10n_it_pos.FiscalReceipt";

    static components = {
        Header,
        Body,
        Footer,
    };

    props = useProps({
        order: t.instanceOf(PosOrder).optional(), // To keep backward compatibility
        isFiscal: t.boolean().optional(true),
        isBasicPrint: t.boolean().optional(false),
        isEarlyPrint: t.boolean().optional(false),
    });
}
