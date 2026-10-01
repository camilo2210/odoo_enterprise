/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import { CallFlowField } from "@voip/call_flow/call_flow_field";
import {
    computeCallGroupNodeHeight,
    computeQueueNodeHeight,
} from "@voip/flow_editor/node_types/content_height";
import { setTerminalRecordNode } from "@voip/flow_editor/node_types/terminal_record_flow_node";
import { flowNodeTypeRegistry } from "@voip/flow_editor/node_types/index";

test.tags("headless");

function makeOrm(type, itemCount) {
    return {
        async read(model) {
            if (model === "voip.ivr") {
                return [{ id: 1, display_name: "IVR", option_ids: [1, 2, 3, 4] }];
            }
            if (model === "voip.ivr.option") {
                return [
                    { id: 1, digit: "1" },
                    { id: 2, digit: "2" },
                    { id: 3, digit: "3" },
                    { id: 4, digit: "4" },
                ];
            }
            if (model === "voip.call.group") {
                return [
                    {
                        id: 1,
                        display_name: "Group",
                        user_display_names: Array(itemCount),
                    },
                ];
            }
            return [{ id: 1, display_name: type }];
        },
        async searchCount() {
            return itemCount;
        },
    };
}

async function selectRecord(type, itemCount, { manuallyResized = false } = {}) {
    const draft = flowNodeTypeRegistry.create(type, { id: type });
    draft.data.manuallyResized = manuallyResized;
    if (manuallyResized) {
        draft.size.height = 999;
    }
    await setTerminalRecordNode(makeOrm(type, itemCount), draft, 1);
    return draft;
}

describe("variable node heights", () => {
    test("height helpers enforce their minimum and grow with content", () => {
        expect(computeQueueNodeHeight(0)).toBe(140);
        expect(computeQueueNodeHeight(4)).toBe(202);
        expect(computeCallGroupNodeHeight(0)).toBe(160);
        expect(computeCallGroupNodeHeight(6)).toBe(222);
    });

    test("initial record selection computes IVR, Queue and Call Group heights", async () => {
        expect((await selectRecord("ivr", 4)).size.height).toBe(304);
        expect((await selectRecord("queue", 4)).size.height).toBe(202);
        expect((await selectRecord("call_group", 6)).size.height).toBe(222);
    });

    test("initial record selection preserves a manual height", async () => {
        for (const type of ["ivr", "queue", "call_group"]) {
            expect((await selectRecord(type, 6, { manuallyResized: true })).size.height).toBe(999);
        }
    });

    test('creating a record via "Create and edit..." loads its display name', async () => {
        for (const type of ["queue", "call_group"]) {
            const draft = flowNodeTypeRegistry.create(type, { id: type });
            await setTerminalRecordNode(makeOrm(type, 4), draft, 1);
            expect(draft.record.data.display_name).toBe(type === "queue" ? "queue" : "Group");
        }
    });

    test("ending a resize marks the node as manually resized", () => {
        let updatedNode;
        const node = {
            id: "queue",
            data: { label: "Queue" },
            position: { x: 0, y: 0 },
            size: { width: 200, height: 300 },
        };
        CallFlowField.prototype.onNodeResize.call(
            { updateNode: (value) => (updatedNode = value) },
            { node, phase: "move" }
        );
        expect(updatedNode).toBe(undefined);

        CallFlowField.prototype.onNodeResize.call(
            { updateNode: (value) => (updatedNode = value) },
            { node, phase: "end" }
        );
        expect(updatedNode.data).toEqual({ manuallyResized: true });
    });
});
