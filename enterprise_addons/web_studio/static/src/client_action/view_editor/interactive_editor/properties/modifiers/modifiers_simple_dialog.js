import { Component, proxy, signal, t, usePlugin, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { evaluateExpr } from "@web/core/py_js/py";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";
import { DebugModePlugin } from "@web/core/debug_mode_plugin";

export class ModifiersSimpleDialog extends Component {
    static components = { Dialog };
    static template = "web_studio.ViewEditor.InteractiveEditorProperties.ModifiersSimpleDialog";
    props = useProps({
        close: t.function(),
        expression: t.string(),
        onConfirm: t.function(),
    });

    confirmRef = signal.ref();
    debugMode = usePlugin(DebugModePlugin);

    setup() {
        this.notification = useService("notification");
        this.state = proxy({
            expression: this.props.expression,
        });
    }

    updateCondition(value) {
        this.state.expression = value;
    }

    async onConfirm() {
        this.confirmRef().disabled = true;
        const evalContext = { ...user.context };
        try {
            evaluateExpr(this.state.expression, evalContext);
        } catch {
            if (this.confirmRef()) {
                this.confirmRef().disabled = false;
            }
            this.notification.add(_t("Expression is invalid. Please correct it"), {
                type: "danger",
            });
            return;
        }
        this.props.onConfirm(this.state.expression);
        this.props.close();
    }

    onDiscard() {
        this.props.close();
    }
}
