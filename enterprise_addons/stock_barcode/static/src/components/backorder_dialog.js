import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { Component, t, useProps } from "@odoo/owl";

export class BackorderDialog extends Component {
    static components = { Dialog };
    static template = "stock_barcode.BackorderDialog";

    props = useProps({
        displayUoM: t.boolean(),
        uncompletedLines: t.array(),
        onApply: t.function(),
        pickingIds: t.array(),
        backorderMode: t.string(),
        close: t.function(),
    });

    setup() {
        this.mode = this.props.backorderMode;
        this.isNever = this.mode === "never";
        this.isAsk = this.mode === "ask";

        this.description = {
            always: _t("If you validate now, the remaining products will be added to a backorder."),
            never: _t("If you validate, the remaining products will never be done."),
            ask: _t(
                "Create a backorder if you expect to process the remaining products later. " +
                    "Do not create a backorder if you will not process the remaining products."
            ),
        }[this.mode];

        this.titleLabel = this.isNever ? _t("Missing") : _t("Backorder");
        this.createLabel = this.isAsk ? _t("Create Backorder") : _t("Validate");
        this.noBackorderLabel = this.isAsk ? _t("No Backorder") : _t("Validate");
        this.discardLabel = this.isAsk ? _t("Discard") : _t("Stay on transfer");
    }

    async _onBackorder(createBackorder) {
        const context = createBackorder
            ? {}
            : { picking_ids_not_to_backorder: this.props.pickingIds };
        await this.props.onApply(context);
        this.props.close();
    }
}
