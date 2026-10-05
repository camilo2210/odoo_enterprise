import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("ivr", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Open a Menu"),
    description: _t("Route the call according to the caller's input."),
    icon: "format_list_numbered",
    sequence: 45,
    size: { width: 200, height: 200 },
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('An "ivr" flow node requires an id.');
        }
        return {
            id,
            type: "ivr",
            position,
            size: { width: 200, height: 200 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [],
            data: { label: _t("Open a Menu") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select a menu before applying.");
    },
});
