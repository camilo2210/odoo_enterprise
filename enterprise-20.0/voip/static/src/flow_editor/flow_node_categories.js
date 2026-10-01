import { _t } from "@web/core/l10n/translation";

import { flowNodeTypeRegistry } from "./flow_node_type_registry";

export const FLOW_NODE_CATEGORIES = Object.freeze({
    FLOW_CONTROL: "flow_control",
    CALL_ROUTING: "call_routing",
});

flowNodeTypeRegistry.addCategory(FLOW_NODE_CATEGORIES.FLOW_CONTROL, {
    label: _t("Flow control"),
    sequence: 40,
});

flowNodeTypeRegistry.addCategory(FLOW_NODE_CATEGORIES.CALL_ROUTING, {
    label: _t("Call routing"),
    sequence: 30,
});
