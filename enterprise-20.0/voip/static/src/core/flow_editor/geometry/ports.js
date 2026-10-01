import { getNodeSize } from "./nodes";

export const DEFAULT_NODE_HEADER_HEIGHT = 40;

/**
 * @param {import("../flow_types").FlowNode} node
 * @param {import("../flow_types").FlowSize} size
 * @param {number} defaultHeaderHeight
 * @returns {number}
 */
export function getNodeHeaderHeight(node, size, defaultHeaderHeight) {
    if (node.shape === "circle") {
        return 0;
    }
    return Math.min(Math.max(node.headerHeight ?? defaultHeaderHeight, 0), size.height);
}

/**
 * Return the vertical offset of a port from the top edge of its node.
 *
 * @param {import("../flow_types").FlowNode} node
 * @param {import("../flow_types").FlowPortId} portId
 * @param {import("../flow_types").FlowSize} defaultSize
 * @param {number} [defaultHeaderHeight]
 * @returns {number | null}
 */
export function getPortOffset(
    node,
    portId,
    defaultSize,
    defaultHeaderHeight = DEFAULT_NODE_HEADER_HEIGHT
) {
    const size = getNodeSize(node, defaultSize);
    const headerHeight = getNodeHeaderHeight(node, size, defaultHeaderHeight);
    const bodyHeight = size.height - headerHeight;
    if (node.input?.id === portId) {
        return headerHeight + bodyHeight / 2;
    }
    const outputIndex = node.outputs.findIndex((output) => output.id === portId);
    if (outputIndex === -1) {
        return null;
    }
    return headerHeight + (bodyHeight * (outputIndex + 1)) / (node.outputs.length + 1);
}

/**
 * Return the anchor of a port in flow world coordinates.
 *
 * The single input is centered on the left edge of the body. Outputs are
 * distributed on the right edge of the body in their declared order.
 *
 * @param {import("../flow_types").FlowNode} node
 * @param {import("../flow_types").FlowPortId} portId
 * @param {import("../flow_types").FlowSize} defaultSize
 * @param {number} [defaultHeaderHeight]
 * @returns {import("../flow_types").FlowPosition | null}
 */
export function getPortAnchor(
    node,
    portId,
    defaultSize,
    defaultHeaderHeight = DEFAULT_NODE_HEADER_HEIGHT
) {
    const size = getNodeSize(node, defaultSize);
    const offset = getPortOffset(node, portId, defaultSize, defaultHeaderHeight);
    if (offset === null) {
        return null;
    }
    return {
        x: node.input?.id === portId ? node.position.x : node.position.x + size.width,
        y: node.position.y + offset,
    };
}
