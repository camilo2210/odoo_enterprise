import { Dialog } from "@web/core/dialog/dialog";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

import { Component, useProps, signal, t, usePlugin } from "@odoo/owl";

export class FieldSelectorDialog extends Component {
    static template = "web_studio.FieldSelectorDialog";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
        onConfirm: t.function(),
        fields: t.array(),
        showNew: t.boolean().optional(false),
    });
    selectRef = signal.ref();

    debugMode = usePlugin(DebugModePlugin);

    onConfirm() {
        const field = this.selectRef().value;
        this.props.onConfirm(field);
        this.props.close();
    }
    onCancel() {
        this.props.close();
    }
}
