import { Component, useProps, t } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { formatDateTime } from "@web/core/l10n/dates";
import { PrintRecMessage, PrintNormal } from "@l10n_it_pos/app/fiscal_printer/commands";
import { Heading } from "@l10n_it_pos/app/documents/entities";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

export class Footer extends Component {
    static template = "l10n_it_pos.FiscalDocumentFooter";

    static components = {
        PrintRecMessage,
        PrintNormal,
    };

    props = useProps({
        order: t.instanceOf(PosOrder),
        isBasicPrint: t.boolean().optional(),
        isFiscal: t.boolean().optional(true),
    });

    async setup() {
        this.order = this.props.order;
    }

    get footers() {
        Heading.resetIndex();
        const headings = [
            new Heading(_t("Powered by Odoo")),
            new Heading(this.order.name),
            new Heading(formatDateTime(this.order.date_order)),
        ];

        return headings.filter(Boolean);
    }
}
