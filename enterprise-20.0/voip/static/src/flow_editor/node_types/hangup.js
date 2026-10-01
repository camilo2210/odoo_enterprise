import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { HangupFlowNode } from "./hangup_flow_node";

flowNodeTypeRegistry.add("hangup", {
    Component: HangupFlowNode,
    category: FLOW_NODE_CATEGORIES.FLOW_CONTROL,
    label: _t("Hang Up"),
    description: _t("End the current call."),
    icon: "phone_disabled",
    icon_class: "oi-filled",
    sequence: 20,
    shape: "circle",
    size: { width: 64, height: 64 },
    terminal: true,
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('A "hangup" flow node requires an id.');
        }
        return {
            id,
            type: "hangup",
            position,
            shape: "circle",
            size: { width: 64, height: 64 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow"],
            },
            outputs: [],
            data: { label: _t("Hang Up") },
            deletable: true,
        };
    },
});
