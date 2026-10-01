/**
 * Small clearance kept off an obstacle's edge. Obstacles are already expanded
 * by the caller's own `padding`, so this only needs to clear the exact
 * (inclusive) boundary `segmentIntersectsRect` treats as a collision.
 */
const BOUNDARY_MARGIN = 1;

/**
 * Default vertical offset used by the row corridor when no obstacle informs
 * a better one (e.g. no obstacle at all, but the target sits behind the
 * source and a corridor is still the only valid shape).
 */
const DEFAULT_CORRIDOR_OFFSET = 40;

/**
 * @param {[number, number]} start
 * @param {[number, number]} end
 * @param {import("./nodes").FlowRect} rect
 * @returns {boolean}
 */
export function segmentIntersectsRect(start, end, rect) {
    const [startX, startY] = start;
    const [endX, endY] = end;
    if (startX === endX) {
        const [minY, maxY] = [startY, endY].sort((a, b) => a - b);
        return startX >= rect.x1 && startX <= rect.x2 && maxY >= rect.y1 && minY <= rect.y2;
    }
    if (startY === endY) {
        const [minX, maxX] = [startX, endX].sort((a, b) => a - b);
        return startY >= rect.y1 && startY <= rect.y2 && maxX >= rect.x1 && minX <= rect.x2;
    }
    return false;
}

/**
 * @param {[number, number][]} points
 * @returns {[number, number][]}
 */
function simplifyPoints(points) {
    return points.filter(
        (point, index) =>
            index === 0 || point[0] !== points[index - 1][0] || point[1] !== points[index - 1][1]
    );
}

/**
 * Collapse a point whose incoming and outgoing segments share the same axis
 * and direction: it is a straight continuation, not a genuine corner.
 *
 * @param {[number, number][]} points
 * @returns {[number, number][]}
 */
function mergeCollinearSegments(points) {
    const merged = [];
    for (const point of points) {
        while (merged.length >= 2) {
            const [x0, y0] = merged[merged.length - 2];
            const [x1, y1] = merged[merged.length - 1];
            const incomingX = x1 - x0;
            const incomingY = y1 - y0;
            const outgoingX = point[0] - x1;
            const outgoingY = point[1] - y1;
            const sameAxis =
                (incomingX === 0 && outgoingX === 0) || (incomingY === 0 && outgoingY === 0);
            const sameDirection =
                Math.sign(incomingX) === Math.sign(outgoingX) &&
                Math.sign(incomingY) === Math.sign(outgoingY);
            if (!sameAxis || !sameDirection) {
                break;
            }
            merged.pop();
        }
        merged.push(point);
    }
    return merged;
}

/**
 * Every segment here is axis-aligned, so two consecutive segments can only
 * share an axis by continuing in the same direction — already collapsed by
 * `mergeCollinearSegments` — or by reversing on it. Any same-axis adjacency
 * surviving that merge is therefore necessarily a reversal.
 *
 * @param {[number, number][]} points
 * @returns {boolean}
 */
export function hasReversal(points) {
    for (let index = 1; index < points.length - 1; index++) {
        const [x0, y0] = points[index - 1];
        const [x1, y1] = points[index];
        const [x2, y2] = points[index + 1];
        const incomingX = x1 - x0;
        const incomingY = y1 - y0;
        const outgoingX = x2 - x1;
        const outgoingY = y2 - y1;
        if ((incomingX === 0 && outgoingX === 0) || (incomingY === 0 && outgoingY === 0)) {
            return true;
        }
    }
    return false;
}

/**
 * @param {[number, number][]} points
 * @param {number} [radius]
 * @returns {string}
 */
export function polylineToRoundedPath(points, radius = 8) {
    if (points.length < 2) {
        return "";
    }
    const path = [`M ${points[0][0]} ${points[0][1]}`];
    let previousPoint = points[0];
    for (let index = 1; index < points.length; index++) {
        const currentPoint = points[index];
        const nextPoint = points[index + 1];
        if (nextPoint) {
            const incomingX = currentPoint[0] - previousPoint[0];
            const incomingY = currentPoint[1] - previousPoint[1];
            const outgoingX = nextPoint[0] - currentPoint[0];
            const outgoingY = nextPoint[1] - currentPoint[1];
            const isTurn =
                (incomingX === 0 && outgoingY === 0) || (incomingY === 0 && outgoingX === 0);
            if (isTurn) {
                const incomingLength = Math.max(1, Math.hypot(incomingX, incomingY));
                const outgoingLength = Math.max(1, Math.hypot(outgoingX, outgoingY));
                const cornerRadius = Math.min(
                    Math.max(0, radius),
                    incomingLength / 2,
                    outgoingLength / 2
                );
                const before = [
                    currentPoint[0] - (incomingX / incomingLength) * cornerRadius,
                    currentPoint[1] - (incomingY / incomingLength) * cornerRadius,
                ];
                const after = [
                    currentPoint[0] + (outgoingX / outgoingLength) * cornerRadius,
                    currentPoint[1] + (outgoingY / outgoingLength) * cornerRadius,
                ];
                path.push(`L ${before[0]} ${before[1]}`);
                path.push(`Q ${currentPoint[0]} ${currentPoint[1]} ${after[0]} ${after[1]}`);
                previousPoint = after;
                continue;
            }
        }
        path.push(`L ${currentPoint[0]} ${currentPoint[1]}`);
        previousPoint = currentPoint;
    }
    return path.join(" ");
}

/**
 * @param {[number, number][]} points
 * @returns {{ x: number, y: number }}
 */
function getPathMidpoint(points) {
    const lengths = [];
    let totalLength = 0;
    for (let index = 0; index < points.length - 1; index++) {
        const length = Math.hypot(
            points[index + 1][0] - points[index][0],
            points[index + 1][1] - points[index][1]
        );
        lengths.push(length);
        totalLength += length;
    }
    const targetLength = totalLength / 2;
    let walkedLength = 0;
    for (let index = 0; index < lengths.length; index++) {
        if (walkedLength + lengths[index] >= targetLength) {
            const ratio = lengths[index] ? (targetLength - walkedLength) / lengths[index] : 0;
            return {
                x: points[index][0] + (points[index + 1][0] - points[index][0]) * ratio,
                y: points[index][1] + (points[index + 1][1] - points[index][1]) * ratio,
            };
        }
        walkedLength += lengths[index];
    }
    return { x: points[0][0], y: points[0][1] };
}

/**
 * @param {[number, number][]} points
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {boolean}
 */
function pathCollidesWithObstacles(points, obstacles) {
    for (let index = 0; index < points.length - 1; index++) {
        for (const rect of obstacles) {
            if (segmentIntersectsRect(points[index], points[index + 1], rect)) {
                return true;
            }
        }
    }
    return false;
}

/**
 * @param {[number, number][]} points
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {import("./nodes").FlowRect[]} every obstacle hit by at least one segment
 */
function blockingObstacles(points, obstacles) {
    const hits = [];
    for (let index = 0; index < points.length - 1; index++) {
        for (const rect of obstacles) {
            if (
                !hits.includes(rect) &&
                segmentIntersectsRect(points[index], points[index + 1], rect)
            ) {
                hits.push(rect);
            }
        }
    }
    return hits;
}

/**
 * Assemble the true anchors with a candidate's interior route, collapse the
 * result to its genuine corners, and accept it only if it never reverses on
 * an axis it just travelled and never crosses an obstacle — leads included.
 *
 * @param {[number, number]} startPoint
 * @param {[number, number]} endPoint
 * @param {[number, number][]} routePoints
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {[number, number][] | null}
 */
function validateCandidate(startPoint, endPoint, routePoints, obstacles) {
    const points = mergeCollinearSegments(simplifyPoints([startPoint, ...routePoints, endPoint]));
    if (hasReversal(points) || pathCollidesWithObstacles(points, obstacles)) {
        return null;
    }
    return points;
}

/**
 * Shrink a port's mandatory lead stub so it stops short of an obstacle
 * sitting on its row, instead of assuming the full `lead` distance is clear.
 *
 * @param {number} anchorX
 * @param {number} y
 * @param {1 | -1} direction leaving the anchor (+x for a source, -x for a target)
 * @param {number} maxLead
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {number}
 */
function adaptiveLead(anchorX, y, direction, maxLead, obstacles) {
    let limit = maxLead;
    for (const rect of obstacles) {
        if (y < rect.y1 || y > rect.y2) {
            continue;
        }
        const inTheWay = direction > 0 ? rect.x2 >= anchorX : rect.x1 <= anchorX;
        if (!inTheWay) {
            continue;
        }
        const distanceToEdge = direction > 0 ? rect.x1 - anchorX : anchorX - rect.x2;
        limit = Math.min(limit, Math.max(0, distanceToEdge - BOUNDARY_MARGIN));
    }
    return limit;
}

/**
 * A single elbow, only possible when the target column is at or ahead of the
 * source column — an orthogonal path whose mandatory leads both point +x
 * cannot fold back on itself with a single bend otherwise.
 *
 * @param {[number, number]} A
 * @param {[number, number]} B
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {[number, number][][]}
 */
function elbowCandidates(A, B, obstacles) {
    if (A[1] === B[1] && B[0] >= A[0]) {
        return [[A, B]];
    }
    if (B[0] < A[0]) {
        return [];
    }
    const candidates = [
        [A, [B[0], A[1]], B], // turn late: keep the source row as long as possible
        [A, [A[0], B[1]], B], // turn early: reach the target column immediately
    ];
    const blocked = new Set();
    for (const candidate of candidates) {
        for (const rect of blockingObstacles(candidate, obstacles)) {
            blocked.add(rect);
        }
    }
    for (const rect of blocked) {
        const rightX = Math.min(B[0], Math.max(A[0], rect.x2 + BOUNDARY_MARGIN));
        const leftX = Math.max(A[0], Math.min(B[0], rect.x1 - BOUNDARY_MARGIN));
        candidates.push([A, [rightX, A[1]], [rightX, B[1]], B]);
        candidates.push([A, [leftX, A[1]], [leftX, B[1]], B]);
    }
    return candidates;
}

/**
 * A row corridor (vertical, then horizontal, then vertical): the only shape
 * that also works when the target sits behind the source, since its middle
 * horizontal run isn't adjacent to either mandatory (+x) lead.
 *
 * @param {[number, number]} A
 * @param {[number, number]} B
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {[number, number][][]}
 */
function corridorCandidates(A, B, obstacles) {
    // Only obstacles whose x-range overlaps the corridor's own horizontal
    // span can ever block one of its legs. Restricting candidate rows to
    // these keeps the chosen route stable when an unrelated, distant node
    // moves — it can no longer shift which gap looks best for a connection
    // it was never actually near.
    const minX = Math.min(A[0], B[0]);
    const maxX = Math.max(A[0], B[0]);
    const relevantObstacles = obstacles.filter((rect) => rect.x2 >= minX && rect.x1 <= maxX);
    const rows = new Set();
    for (const rect of relevantObstacles) {
        rows.add(rect.y1);
        rows.add(rect.y2);
    }
    const sorted = [...rows].sort((rowA, rowB) => rowA - rowB);
    const gapRows = [];
    for (let index = 0; index < sorted.length - 1; index++) {
        const gapStart = sorted[index] + BOUNDARY_MARGIN;
        const gapEnd = sorted[index + 1] - BOUNDARY_MARGIN;
        if (gapEnd > gapStart) {
            let row = (gapStart + gapEnd) / 2;
            // A row exactly on A[1]/B[1] would collapse the corridor back
            // into a same-row shape instead of a genuine detour — nudge off
            // it, staying inside the gap, so the shape stays meaningful.
            if (row === A[1] || row === B[1]) {
                row =
                    row + BOUNDARY_MARGIN <= gapEnd ? row + BOUNDARY_MARGIN : row - BOUNDARY_MARGIN;
            }
            gapRows.push(row);
        }
    }
    const targetRow = (A[1] + B[1]) / 2;
    gapRows.sort((rowA, rowB) => Math.abs(rowA - targetRow) - Math.abs(rowB - targetRow));
    const edgeRows = sorted.length
        ? [sorted[0] - BOUNDARY_MARGIN, sorted[sorted.length - 1] + BOUNDARY_MARGIN]
        : [];
    const defaultRows = [targetRow + DEFAULT_CORRIDOR_OFFSET, targetRow - DEFAULT_CORRIDOR_OFFSET];
    return [...gapRows, ...edgeRows, ...defaultRows].map((y) => [A, [A[0], y], [B[0], y], B]);
}

/**
 * Try every shape, simplest (fewest bends) first, and return the first one
 * that survives full validation.
 *
 * @param {[number, number]} startPoint
 * @param {[number, number]} endPoint
 * @param {[number, number]} A
 * @param {[number, number]} B
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {[number, number][] | null}
 */
function findValidRoute(startPoint, endPoint, A, B, obstacles) {
    for (const candidate of elbowCandidates(A, B, obstacles)) {
        const points = validateCandidate(startPoint, endPoint, candidate, obstacles);
        if (points) {
            return points;
        }
    }
    for (const candidate of corridorCandidates(A, B, obstacles)) {
        const points = validateCandidate(startPoint, endPoint, candidate, obstacles);
        if (points) {
            return points;
        }
    }
    return null;
}

/**
 * Last-resort route for the pathological case where an obstacle sits astride
 * one port's own column, defeating every fixed-shape candidate above. Clears
 * one blocking obstacle at a time — each hop permanently gets past whichever
 * obstacle triggered it, so the walk is bounded by the obstacle count and
 * always terminates. This should never trigger on a hand-drawn call-flow
 * diagram; it exists only so "never overlap a node" holds unconditionally,
 * even if that means exceeding 4 bends in this one residual case.
 *
 * @param {[number, number]} A
 * @param {[number, number]} B
 * @param {import("./nodes").FlowRect[]} obstacles
 * @returns {[number, number][]}
 */
export function staircaseRoute(A, B, obstacles) {
    const points = [A];
    let current = A;
    let guard = obstacles.length + 4;
    while (guard-- > 0) {
        const direct = [current, [B[0], current[1]], B];
        const hits = blockingObstacles(direct, obstacles);
        if (!hits.length) {
            points.push([B[0], current[1]], B);
            return points;
        }
        const rect = hits[0];
        if (segmentIntersectsRect(current, [B[0], current[1]], rect)) {
            current = [
                current[0],
                current[1] <= (rect.y1 + rect.y2) / 2
                    ? rect.y1 - BOUNDARY_MARGIN
                    : rect.y2 + BOUNDARY_MARGIN,
            ];
        } else {
            current = [
                current[0] <= (rect.x1 + rect.x2) / 2
                    ? rect.x1 - BOUNDARY_MARGIN
                    : rect.x2 + BOUNDARY_MARGIN,
                current[1],
            ];
        }
        points.push(current);
    }
    // The guard should never be exhausted in practice; keep the result
    // orthogonal even here rather than closing with a diagonal segment.
    if (current[0] !== B[0] && current[1] !== B[1]) {
        points.push([current[0], B[1]]);
    }
    points.push(B);
    return points;
}

/**
 * Vertical clearances tried, closest to the node first, before falling back
 * to the smallest one unconditionally.
 */
const SELF_LOOP_MARGINS = [40, 72, 104];

/**
 * Build the route for a connection whose source and target are the same
 * node.
 *
 * `buildOrthogonalPath`'s obstacle math treats an anchor sitting on an
 * obstacle's own boundary as instantly blocked - necessary so every *other*
 * connection stops right at its port - which means the node a self-loop
 * belongs to can never be included in its own `obstacles`. Routed with that
 * exclusion, the direct output->input path cuts straight across the node's
 * body, hidden behind it since connections render under nodes. This instead
 * drops the loop below (or above, whichever side the output port already
 * leans toward) the node's own bounding box, clearing it by construction.
 *
 * @param {Object} params
 * @param {import("../flow_types").FlowPosition} params.start
 * @param {import("../flow_types").FlowPosition} params.end
 * @param {import("./nodes").FlowRect} params.nodeRect the loop's own node - never in `obstacles`
 * @param {import("./nodes").FlowRect[]} [params.obstacles] every *other* node
 * @param {number} [params.lead]
 * @param {number} [params.cornerRadius]
 * @returns {{ points: [number, number][], path: string, midpoint: { x: number, y: number } }}
 */
export function buildSelfLoopPath({
    start,
    end,
    nodeRect,
    obstacles = [],
    lead = 32,
    cornerRadius = 8,
}) {
    const startPoint = [start.x, start.y];
    const endPoint = [end.x, end.y];
    const A = [start.x + adaptiveLead(start.x, start.y, 1, lead, obstacles), start.y];
    const B = [end.x - adaptiveLead(end.x, end.y, -1, lead, obstacles), end.y];

    const preferBelow = start.y >= (nodeRect.y1 + nodeRect.y2) / 2;
    const sides = preferBelow
        ? [
              { edge: nodeRect.y2, sign: 1 },
              { edge: nodeRect.y1, sign: -1 },
          ]
        : [
              { edge: nodeRect.y1, sign: -1 },
              { edge: nodeRect.y2, sign: 1 },
          ];

    for (const { edge, sign } of sides) {
        for (const margin of SELF_LOOP_MARGINS) {
            const loopY = edge + sign * margin;
            const points = validateCandidate(
                startPoint,
                endPoint,
                [A, [A[0], loopY], [B[0], loopY], B],
                obstacles
            );
            if (points) {
                return {
                    points,
                    path: polylineToRoundedPath(points, cornerRadius),
                    midpoint: getPathMidpoint(points),
                };
            }
        }
    }
    const { edge, sign } = sides[0];
    const loopY = edge + sign * SELF_LOOP_MARGINS[0];
    const points = mergeCollinearSegments(
        simplifyPoints([startPoint, A, [A[0], loopY], [B[0], loopY], B, endPoint])
    );
    return {
        points,
        path: polylineToRoundedPath(points, cornerRadius),
        midpoint: getPathMidpoint(points),
    };
}

/**
 * Build an orthogonal route between two anchors that never crosses an
 * obstacle and never reverses direction on an axis it just travelled.
 *
 * Ports always sit on a node's left (input) or right (output) edge, so the
 * mandatory lead in/out of an anchor is always horizontal. A bounded set of
 * shapes is tried in order of visual simplicity — a straight line, a single
 * elbow, a row corridor — each fully validated (every segment, leads
 * included, against every obstacle); a deterministic, terminating sweep is
 * used only if none of them can be made to work.
 *
 * @param {Object} params
 * @param {import("../flow_types").FlowPosition} params.start
 * @param {import("../flow_types").FlowPosition} params.end
 * @param {import("./nodes").FlowRect[]} [params.obstacles]
 * @param {number} [params.padding] kept for backward compatibility; obstacles
 *  are already expanded by the caller's own padding, so it is not reapplied here.
 * @param {number} [params.lead]
 * @param {number} [params.cornerRadius]
 * @returns {{ points: [number, number][], path: string, midpoint: { x: number, y: number } }}
 */
export function buildOrthogonalPath({ start, end, obstacles = [], lead = 32, cornerRadius = 8 }) {
    const startPoint = [start.x, start.y];
    const endPoint = [end.x, end.y];
    const leadOut = adaptiveLead(start.x, start.y, 1, lead, obstacles);
    const leadIn = adaptiveLead(end.x, end.y, -1, lead, obstacles);
    const A = [start.x + leadOut, start.y];
    const B = [end.x - leadIn, end.y];

    const points =
        findValidRoute(startPoint, endPoint, A, B, obstacles) ??
        mergeCollinearSegments(
            simplifyPoints([startPoint, ...staircaseRoute(A, B, obstacles), endPoint])
        );
    return {
        points,
        path: polylineToRoundedPath(points, cornerRadius),
        midpoint: getPathMidpoint(points),
    };
}
