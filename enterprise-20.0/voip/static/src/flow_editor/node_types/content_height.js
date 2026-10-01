/**
 * Natural node height for a "queue" node given its number of agents, so the
 * node is tall enough to show every agent row without shrinking the canvas
 * geometry to a box smaller than what actually gets rendered.
 *
 * @param {number} agentCount
 * @returns {number}
 */
export function computeQueueNodeHeight(agentCount) {
    return Math.max(140, 90 + agentCount * 28);
}

/**
 * Natural node height for a "call_group" node given its number of members.
 *
 * @param {number} memberCount
 * @returns {number}
 */
export function computeCallGroupNodeHeight(memberCount) {
    return Math.max(160, 90 + memberCount * 22);
}
