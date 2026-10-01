import { Component, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

function copyNode(node) {
    return {
        ...node,
        position: { ...node.position },
        ...(node.size ? { size: { ...node.size } } : {}),
        ...(node.record ? { record: { ...node.record, data: { ...node.record.data } } } : {}),
        ...(node.input ? { input: { ...node.input } } : {}),
        outputs: node.outputs.map((output) => ({ ...output })),
        data: { ...node.data },
    };
}

export class FlowNodeConfigurationDialog extends Component {
    static template = "voip.FlowNodeConfigurationDialog";
    static components = { Dialog };

    props = useProps({
        close: t.function(),
        node: t.object(),
        onApply: t.function(),
        onCancel: t.function().optional(() => () => {}),
        registry: t.any(),
    });

    setup() {
        this.draft = proxy(copyNode(this.props.node));
        this.env.dialogData.dismiss = () => this.cancel();
    }

    get applyLabel() {
        return _t("Apply");
    }

    get cancelLabel() {
        return _t("Discard");
    }

    get configComponentProps() {
        return { draft: this.draft };
    }

    get definition() {
        return this.props.registry.get(this.draft.type);
    }

    get title() {
        return _t("Configure node");
    }

    async apply() {
        if ((await this.props.onApply(this.draft)) !== false) {
            this.props.close();
        }
    }

    cancel() {
        this.props.onCancel();
        this.props.close();
    }
}
