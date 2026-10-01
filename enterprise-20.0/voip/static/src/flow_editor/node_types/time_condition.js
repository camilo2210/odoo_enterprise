import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("time_condition", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Time Condition"),
    description: _t("Route the call depending on whether a Time Condition is open or closed."),
    icon: "schedule",
    sequence: 90,
    size: { width: 200, height: 110 },
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('A "time_condition" flow node requires an id.');
        }
        return {
            id,
            type: "time_condition",
            position,
            size: { width: 200, height: 110 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [
                {
                    id: "open",
                    direction: "output",
                    label: _t("Open"),
                    provides: "flow",
                    maxConnections: 1,
                },
                {
                    id: "closed",
                    direction: "output",
                    label: _t("Closed"),
                    provides: "flow",
                    maxConnections: 1,
                },
            ],
            data: { label: _t("Time Condition") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select a Time Condition before applying.");
    },
});
