import { _t } from "@web/core/l10n/translation";
import { Component, proxy, t, useProps } from "@odoo/owl";
import {
    ConfirmationDialog,
    confirmationDialogProps,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { formatDate, parseDateTime } from "@web/core/l10n/dates";

export class SuggestBatchDialogLine extends Component {
    props = useProps({
        picking: t.object(),
        selected: t.boolean().optional(),
        onClick: t.function(),
    });
    static template = "stock_barcode.SuggestBatchDialog.Line";

    setup() {
        this.date = formatDate(parseDateTime(this.props.picking.date));
    }

    onClick() {
        if (!this.props.selected) {
            this.props.onClick(this.props.picking);
        }
    }
}

export class SuggestBatchDialog extends ConfirmationDialog {
    static components = {
        ...ConfirmationDialog.components,
        SuggestBatchDialogLine,
    };
    props = useProps({
        ...confirmationDialogProps,
        addProduct: t.function(),
        body: t.string(),
        candidates: t.array(),
        confirmLabel: t.string().optional(_t("Batch Receipts")),
        product: t.object(),
        title: t.string(),
    });
    static template = "stock_barcode.SuggestBatchDialog";

    setup() {
        super.setup();
        this.state = proxy({ selectedPicking: this.props.candidates[0] });
    }

    async _confirm() {
        return this.execButton(this._confirmBatch.bind(this));
    }

    async _confirmBatch() {
        await this.props.confirm(this.state.selectedPicking);
    }

    async onClickAddProduct() {
        return this.execButton(this.props.addProduct);
    }

    async onClickPicking(picking) {
        this.state.selectedPicking = picking;
    }
}
