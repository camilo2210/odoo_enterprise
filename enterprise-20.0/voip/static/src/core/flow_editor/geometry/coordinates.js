const DEFAULT_MIN_SCALE = 0.2;
const DEFAULT_MAX_SCALE = 2;

/**
 * @param {number} scale
 * @param {number} [min]
 * @param {number} [max]
 * @returns {number}
 */
export function clampScale(scale, min = DEFAULT_MIN_SCALE, max = DEFAULT_MAX_SCALE) {
    const normalizedScale = Number.isFinite(scale) ? scale : 1;
    return Math.min(max, Math.max(min, normalizedScale));
}

/**
 * Convert screen coordinates into flow world coordinates.
 *
 * @param {{ x: number, y: number }} point
 * @param {{ left: number, top: number }} canvasRect
 * @param {{ x: number, y: number, scale: number }} viewport
 * @returns {import("../flow_types").FlowPosition}
 */
export function screenToWorld(point, canvasRect, viewport) {
    const scale = clampScale(viewport.scale);
    return {
        x: (point.x - canvasRect.left - viewport.x) / scale,
        y: (point.y - canvasRect.top - viewport.y) / scale,
    };
}

/**
 * Convert flow world coordinates into screen coordinates.
 *
 * @param {import("../flow_types").FlowPosition} point
 * @param {{ left: number, top: number }} canvasRect
 * @param {{ x: number, y: number, scale: number }} viewport
 * @returns {{ x: number, y: number }}
 */
export function worldToScreen(point, canvasRect, viewport) {
    const scale = clampScale(viewport.scale);
    return {
        x: canvasRect.left + viewport.x + point.x * scale,
        y: canvasRect.top + viewport.y + point.y * scale,
    };
}
