import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { StartFlowNode } from "./start_flow_node";

flowNodeTypeRegistry.add("start", {
    Component: StartFlowNode,
    category: FLOW_NODE_CATEGORIES.FLOW_CONTROL,
    label: _t("Start"),
    description: _t("Entry point of the flow."),
    icon: "phone",
    icon_class: "oi-filled",
    palette: false,
    sequence: 10,
    shape: "circle",
    size: { width: 64, height: 64 },
    unique: true,
    create({ id = "start", position = { x: 0, y: 0 } } = {}) {
        return {
            id,
            type: "start",
            position,
            shape: "circle",
            size: { width: 64, height: 64 },
            outputs: [
                {
                    id: "next",
                    direction: "output",
                    provides: "flow",
                    maxConnections: 1,
                },
            ],
            data: { label: _t("Start") },
            deletable: false,
        };
    },
});
