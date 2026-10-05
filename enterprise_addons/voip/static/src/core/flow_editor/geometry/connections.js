import { getNodeRect, getObstacleRects } from "./nodes";
import { getPortAnchor } from "./ports";
import { buildOrthogonalPath, buildSelfLoopPath } from "./router";

/**
 * Build the display geometry of a connection.
 *
 * @param {Object} params
 * @param {import("../flow_types").FlowConnection} params.connection
 * @param {import("../flow_types").FlowNode} params.sourceNode
 * @param {import("../flow_types").FlowNode} params.targetNode
 * @param {import("../flow_types").FlowNode[]} params.nodes
 * @param {import("../flow_types").FlowSize} params.defaultNodeSize
 * @param {number} [params.defaultNodeHeaderHeight]
 * @param {number} [params.obstaclePadding]
 * @param {number} [params.lead]
 * @param {number} [params.cornerRadius]
 * @returns {{ id: import("../flow_types").FlowConnectionId, points: [number, number][], path: string, midpoint: { x: number, y: number } } | null}
 */
export function buildConnectionGeometry({
    connection,
    sourceNode,
    targetNode,
    nodes,
    defaultNodeSize,
    defaultNodeHeaderHeight,
    obstaclePadding = 20,
    lead = 32,
    cornerRadius = 8,
}) {
    if (
        !sourceNode.outputs.some((port) => port.id === connection.sourcePortId) ||
        targetNode.input?.id !== connection.targetPortId
    ) {
        return null;
    }
    const start = getPortAnchor(
        sourceNode,
        connection.sourcePortId,
        defaultNodeSize,
        defaultNodeHeaderHeight
    );
    const end = getPortAnchor(
        targetNode,
        connection.targetPortId,
        defaultNodeSize,
        defaultNodeHeaderHeight
    );
    if (!start || !end) {
        return null;
    }
    const obstacles = getObstacleRects(nodes, {
        defaultSize: defaultNodeSize,
        padding: obstaclePadding,
        excludedNodeIds: new Set([sourceNode.id, targetNode.id]),
    });
    const geometry =
        sourceNode.id === targetNode.id
            ? buildSelfLoopPath({
                  start,
                  end,
                  nodeRect: getNodeRect(sourceNode, defaultNodeSize),
                  obstacles,
                  lead,
                  cornerRadius,
              })
            : buildOrthogonalPath({
                  start,
                  end,
                  obstacles,
                  padding: obstaclePadding,
                  lead,
                  cornerRadius,
              });
    return { id: connection.id, ...geometry };
}
