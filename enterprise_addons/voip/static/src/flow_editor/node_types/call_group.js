import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("call_group", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Call a Group"),
    description: _t("Route the call to a call group."),
    icon: "group",
    icon_class: "oi-filled",
    sequence: 30,
    size: { width: 200, height: 160 },
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('A "call_group" flow node requires an id.');
        }
        return {
            id,
            type: "call_group",
            position,
            size: { width: 200, height: 160 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [
                {
                    id: "no_answer",
                    direction: "output",
                    label: _t("No Answer"),
                    provides: "flow",
                    maxConnections: 1,
                },
            ],
            data: { label: _t("Call a Group") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select a call group before applying.");
    },
});
