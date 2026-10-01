import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("audio_message", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Play Audio"),
    description: _t("Play an audio message, then continue."),
    icon: "volume_up",
    sequence: 50,
    size: { width: 200, height: 120 },
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('An "audio_message" flow node requires an id.');
        }
        return {
            id,
            type: "audio_message",
            position,
            size: { width: 200, height: 120 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [],
            data: { label: _t("Play Audio") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select an audio message before applying.");
    },
});
