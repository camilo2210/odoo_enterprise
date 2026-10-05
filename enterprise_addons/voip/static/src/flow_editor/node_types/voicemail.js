import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("voicemail", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Send to Voicemail"),
    description: _t("Record a voicemail message and end the call."),
    icon: "inbox",
    sequence: 60,
    size: { width: 200, height: 120 },
    terminal: true,
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('A "voicemail" flow node requires an id.');
        }
        return {
            id,
            type: "voicemail",
            position,
            size: { width: 200, height: 120 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [],
            data: { label: _t("Send to Voicemail") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select a voicemail before applying.");
    },
});
