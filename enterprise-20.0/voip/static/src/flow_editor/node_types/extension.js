import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("extension", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Redirect to an Extension"),
    description: _t("Route the call to an extension."),
    icon: "phone",
    icon_class: "oi-filled",
    sequence: 70,
    size: { width: 200, height: 120 },
    terminal: true,
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('An "extension" flow node requires an id.');
        }
        return {
            id,
            type: "extension",
            position,
            size: { width: 200, height: 120 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [],
            data: { label: _t("Redirect to an Extension") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select an extension before applying.");
    },
});
