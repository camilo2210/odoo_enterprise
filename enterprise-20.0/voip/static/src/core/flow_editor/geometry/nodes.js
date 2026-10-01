/**
 * @typedef FlowRect
 * @property {number} x1
 * @property {number} y1
 * @property {number} x2
 * @property {number} y2
 */

/**
 * @param {import("../flow_types").FlowNode} node
 * @param {import("../flow_types").FlowSize} defaultSize
 * @returns {import("../flow_types").FlowSize}
 */
export function getNodeSize(node, defaultSize) {
    const size = node.size || defaultSize;
    if (node.shape === "circle") {
        const diameter = Math.min(size.width, size.height);
        return { width: diameter, height: diameter };
    }
    return size;
}

/**
 * @param {import("../flow_types").FlowNode} node
 * @param {import("../flow_types").FlowSize} defaultSize
 * @returns {FlowRect}
 */
export function getNodeRect(node, defaultSize) {
    const size = getNodeSize(node, defaultSize);
    return {
        x1: node.position.x,
        y1: node.position.y,
        x2: node.position.x + size.width,
        y2: node.position.y + size.height,
    };
}

/**
 * @param {FlowRect} rect
 * @param {number} padding
 * @returns {FlowRect}
 */
export function expandRect(rect, padding) {
    return {
        x1: rect.x1 - padding,
        y1: rect.y1 - padding,
        x2: rect.x2 + padding,
        y2: rect.y2 + padding,
    };
}

/**
 * @param {import("../flow_types").FlowNode[]} nodes
 * @param {Object} options
 * @param {import("../flow_types").FlowSize} options.defaultSize
 * @param {number} [options.padding]
 * @param {Set<import("../flow_types").FlowNodeId>} [options.excludedNodeIds]
 * @returns {FlowRect[]}
 */
export function getObstacleRects(nodes, { defaultSize, padding = 0, excludedNodeIds = new Set() }) {
    return nodes
        .filter((node) => !excludedNodeIds.has(node.id))
        .map((node) => expandRect(getNodeRect(node, defaultSize), padding));
}
