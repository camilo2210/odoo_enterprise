import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("queue", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Send to a Queue"),
    description: _t("Route the call to a queue."),
    icon: "headphones",
    sequence: 40,
    size: { width: 200, height: 140 },
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('A "queue" flow node requires an id.');
        }
        return {
            id,
            type: "queue",
            position,
            size: { width: 200, height: 140 },
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
                {
                    id: "busy",
                    direction: "output",
                    label: _t("Busy"),
                    provides: "flow",
                    maxConnections: 1,
                },
            ],
            data: { label: _t("Send to a Queue") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select a queue before applying.");
    },
});
