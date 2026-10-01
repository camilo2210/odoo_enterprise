import { _t } from "@web/core/l10n/translation";

import { FLOW_NODE_CATEGORIES } from "../flow_node_categories";
import { flowNodeTypeRegistry } from "../flow_node_type_registry";
import { TerminalRecordFlowNode } from "./terminal_record_flow_node";

flowNodeTypeRegistry.add("contact", {
    Component: TerminalRecordFlowNode,
    category: FLOW_NODE_CATEGORIES.CALL_ROUTING,
    label: _t("Call a Contact"),
    description: _t("Route the call to a contact's phone number."),
    icon: "contact_mail",
    icon_class: "oi-filled",
    sequence: 20,
    size: { width: 200, height: 120 },
    terminal: true,
    create({ id, position = { x: 0, y: 0 } } = {}) {
        if (id === undefined) {
            throw new Error('A "contact" flow node requires an id.');
        }
        return {
            id,
            type: "contact",
            position,
            size: { width: 200, height: 120 },
            input: {
                id: "input",
                direction: "input",
                accepts: ["flow", "did_entry", "extension_entry"],
            },
            outputs: [],
            data: { label: _t("Call a Contact") },
            deletable: true,
        };
    },
    validate(node) {
        return node.record?.resId ? true : _t("Select a contact before applying.");
    },
});
