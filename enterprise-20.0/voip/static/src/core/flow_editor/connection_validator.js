/**
 * @typedef FlowConnectionValidation
 * @property {boolean} valid
 * @property {string} [reason]
 */

/**
 * Validate a connection against the graph's structural rules.
 *
 * Cycles between different nodes are intentionally allowed.
 *
 * @param {import("./flow_types").FlowConnection} connection
 * @param {Object} graph
 * @param {import("./flow_types").FlowNode[]} graph.nodes
 * @param {import("./flow_types").FlowConnection[]} graph.connections
 * @param {boolean} [graph.allowSelfConnections]
 * @returns {FlowConnectionValidation}
 */
export function validateConnection(
    connection,
    { nodes, connections, allowSelfConnections = false }
) {
    const sourceNode = nodes.find((node) => node.id === connection.sourceNodeId);
    const targetNode = nodes.find((node) => node.id === connection.targetNodeId);
    if (!sourceNode) {
        return { valid: false, reason: "source_node_missing" };
    }
    if (!targetNode) {
        return { valid: false, reason: "target_node_missing" };
    }
    const sourcePort = sourceNode.outputs.find(
        (port) => port.id === connection.sourcePortId && port.direction === "output"
    );
    if (!sourcePort) {
        return { valid: false, reason: "source_port_missing" };
    }
    const targetPort =
        targetNode.input?.id === connection.targetPortId && targetNode.input.direction === "input"
            ? targetNode.input
            : null;
    if (!targetPort) {
        return { valid: false, reason: "target_port_missing" };
    }
    if (!allowSelfConnections && sourceNode.id === targetNode.id) {
        return { valid: false, reason: "self_connection" };
    }
    if (
        connections.some(
            (existing) =>
                existing.sourceNodeId === connection.sourceNodeId &&
                existing.sourcePortId === connection.sourcePortId &&
                existing.targetNodeId === connection.targetNodeId &&
                existing.targetPortId === connection.targetPortId
        )
    ) {
        return { valid: false, reason: "duplicate" };
    }
    const sourceConnectionCount = connections.filter(
        (existing) =>
            existing.sourceNodeId === connection.sourceNodeId &&
            existing.sourcePortId === connection.sourcePortId
    ).length;
    if (
        sourcePort.maxConnections !== undefined &&
        sourceConnectionCount >= sourcePort.maxConnections
    ) {
        return { valid: false, reason: "source_saturated" };
    }
    const targetConnectionCount = connections.filter(
        (existing) =>
            existing.targetNodeId === connection.targetNodeId &&
            existing.targetPortId === connection.targetPortId
    ).length;
    if (
        targetPort.maxConnections !== undefined &&
        targetConnectionCount >= targetPort.maxConnections
    ) {
        return { valid: false, reason: "target_saturated" };
    }
    if (
        targetPort.accepts !== undefined &&
        (!sourcePort.provides || !targetPort.accepts.includes(sourcePort.provides))
    ) {
        return { valid: false, reason: "incompatible_ports" };
    }
    return { valid: true };
}

/**
 * Normalize the result returned by a consumer's synchronous `canConnect` hook.
 *
 * @param {boolean | string | FlowConnectionValidation} result
 * @returns {FlowConnectionValidation}
 */
export function normalizeConnectionValidation(result) {
    if (result === true || result === undefined) {
        return { valid: true };
    }
    if (result === false) {
        return { valid: false, reason: "consumer_rejected" };
    }
    if (typeof result === "string") {
        return { valid: false, reason: result };
    }
    if (typeof result?.valid === "boolean") {
        return result;
    }
    return { valid: false, reason: "invalid_consumer_validation" };
}
