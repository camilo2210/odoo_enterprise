import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";

class OutcallFlowNode extends Component {
    static template = "voip.OutcallFlowNode";

    props = useProps({
        node: t.object(),
        readonly: t.boolean(),
    });

    get extension() {
        return this.props.node.data.extension || _t("No extension");
    }

    get label() {
        return _t("Redirect to an External Number");
    }

    get headerStyle() {
        return `height: ${this.props.node.headerHeight ?? 40}px;`;
    }
}

class OutcallFlowNodeConfig extends Component {
    static template = "voip.OutcallFlowNodeConfig";

    props = useProps({
        draft: t.object(),
    });

    onExtensionInput(ev) {
        this.props.draft.data.extension = ev.target.value;
    }
}

flowNodeTypeRegistry.add("outcall", {
    Component: OutcallFlowNode,
    ConfigComponent: OutcallFlowNodeConfig,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Redirect to an External Number"),
    description: _t("Route the call to an external extension."),
    icon: "open_in_new",
    sequence: 80,
    size: { width: 200, height: 120 },
    terminal: true,
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('An "outcall" flow node requires an id.');
        }
        return {
            id,
            type: "outcall",
            position,
            size: { width: 200, height: 120 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [],
            data: {
                extension: "",
                label: _t("Redirect to an External Number"),
            },
            deletable: true,
        };
    },
    validate(node) {
        const extension = (node.data.extension || "").trim();
        return /^\+?\d+$/.test(extension) ? true : _t("Enter a valid extension before applying.");
    },
});
