import { Component, useProps, t } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class FailureDialog extends Component {
    static template = "pos_tyro.FailureDialog";
    static components = { Dialog };
    props = useProps({
        result: t.string(),
        hasReceipt: t.boolean(),
        printReceipt: t.function(),
        close: t.function(),
    });
}
