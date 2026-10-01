import { Dialog } from "@web/core/dialog/dialog";
import { Component, t, useProps } from "@odoo/owl";

export class ApplyQuantDialog extends Component {
    static components = { Dialog };
    static template = "stock_barcode.ApplyQuantDialog";

    props = useProps({
        onApply: t.function([]),
        onApplyAll: t.function([]),
        close: t.function([]),
    });

    onApply() {
        this.props.onApply();
        this.props.close();
    }

    onApplyAll() {
        this.props.onApplyAll();
        this.props.close();
    }
}
