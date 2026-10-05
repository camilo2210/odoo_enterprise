/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { validateConnection } from "@voip/core/flow_editor/connection_validator";

test.tags("headless");

function node(id, { accepts = ["flow"], provides = "flow", maxConnections } = {}) {
    return {
        id,
        outputs: [
            {
                id: "output",
                direction: "output",
                provides,
                maxConnections,
            },
        ],
        input: {
            id: "input",
            direction: "input",
            accepts,
            maxConnections,
        },
    };
}

function connection(id, sourceNodeId, targetNodeId) {
    return {
        id,
        sourceNodeId,
        sourcePortId: "output",
        targetNodeId,
        targetPortId: "input",
    };
}

function validation(graphConnection, nodes, connections = []) {
    return validateConnection(graphConnection, { nodes, connections });
}

describe("validateConnection", () => {
    test("rejects a self connection", () => {
        const graphNode = node("node");
        expect(validation(connection("self", "node", "node"), [graphNode])).toEqual({
            valid: false,
            reason: "self_connection",
        });
    });

    test("accepts a cycle between distinct nodes", () => {
        const nodes = [node("first"), node("second")];
        const existing = connection("forward", "first", "second");
        expect(validation(connection("back", "second", "first"), nodes, [existing])).toEqual({
            valid: true,
        });
    });

    test("rejects a duplicate connection", () => {
        const nodes = [node("first"), node("second")];
        const existing = connection("existing", "first", "second");
        expect(validation(connection("duplicate", "first", "second"), nodes, [existing])).toEqual({
            valid: false,
            reason: "duplicate",
        });
    });

    test("rejects a saturated source port", () => {
        const nodes = [
            node("source", { maxConnections: 1 }),
            node("first-target"),
            node("second-target"),
        ];
        const existing = connection("existing", "source", "first-target");
        expect(validation(connection("new", "source", "second-target"), nodes, [existing])).toEqual(
            {
                valid: false,
                reason: "source_saturated",
            }
        );
    });

    test("rejects a saturated target port", () => {
        const nodes = [
            node("first-source"),
            node("second-source"),
            node("target", { maxConnections: 1 }),
        ];
        const existing = connection("existing", "first-source", "target");
        expect(validation(connection("new", "second-source", "target"), nodes, [existing])).toEqual(
            {
                valid: false,
                reason: "target_saturated",
            }
        );
    });

    test("rejects incompatible port types", () => {
        const nodes = [
            node("source", { provides: "audio" }),
            node("target", { accepts: ["flow"] }),
        ];
        expect(validation(connection("connection", "source", "target"), nodes)).toEqual({
            valid: false,
            reason: "incompatible_ports",
        });
    });
});
