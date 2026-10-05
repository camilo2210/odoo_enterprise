/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { flowNodeTypeRegistry } from "@voip/flow_editor/node_types/index";

test.tags("headless");

const NODE_EXPECTATIONS = {
    audio_message: { input: true, outputs: [], requiresRecord: true },
    call_group: { input: true, outputs: ["no_answer"], requiresRecord: true },
    contact: { input: true, outputs: [], requiresRecord: true, terminal: true },
    extension: { input: true, outputs: [], requiresRecord: true, terminal: true },
    hangup: { input: true, outputs: [], terminal: true },
    ivr: { input: true, outputs: [], requiresRecord: true },
    outcall: { input: true, outputs: [], requiresExtension: true, terminal: true },
    queue: { input: true, outputs: ["no_answer", "busy"], requiresRecord: true },
    start: { input: false, outputs: ["next"], unique: true },
    time_condition: {
        input: true,
        outputs: ["open", "closed"],
        requiresRecord: true,
    },
    user: { input: true, outputs: [], requiresRecord: true, terminal: true },
    voicemail: { input: true, outputs: [], requiresRecord: true, terminal: true },
};

describe("Call Flow node types", () => {
    test("declare ports coherent with their routing role", () => {
        for (const [type, expected] of Object.entries(NODE_EXPECTATIONS)) {
            const node = flowNodeTypeRegistry.create(type, { id: type });
            expect(Boolean(node.input)).toBe(expected.input);
            if (node.input) {
                expect(node.input.direction).toBe("input");
                expect(node.input.accepts).toInclude("flow");
            }
            expect(node.outputs.map(({ id }) => id)).toEqual(expected.outputs);
            for (const output of node.outputs) {
                expect(output.direction).toBe("output");
                expect(output.provides).toBe("flow");
                expect(output.maxConnections).toBe(1);
            }
            expect(flowNodeTypeRegistry.get(type).terminal).toBe(expected.terminal);
            expect(flowNodeTypeRegistry.get(type).unique).toBe(Boolean(expected.unique));
        }
    });

    test("reject nodes whose required configuration is missing", () => {
        for (const [type, expected] of Object.entries(NODE_EXPECTATIONS)) {
            const definition = flowNodeTypeRegistry.get(type);
            const node = flowNodeTypeRegistry.create(type, { id: type });
            if (expected.requiresRecord) {
                expect(definition.validate(node)).not.toBe(true);
                node.record = { resModel: "test.model", resId: 1 };
                expect(definition.validate(node)).toBe(true);
            } else if (expected.requiresExtension) {
                expect(definition.validate(node)).not.toBe(true);
                node.data.extension = "+32470000000";
                expect(definition.validate(node)).toBe(true);
            } else {
                expect(definition.validate).toBe(undefined);
            }
        }
    });
});
