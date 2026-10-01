/** @odoo-module **/

import { describe, expect, test } from "@odoo/hoot";
import {
    buildOrthogonalPath,
    hasReversal,
    segmentIntersectsRect,
    staircaseRoute,
} from "@voip/core/flow_editor/geometry/router";

test.tags("headless");

/**
 * @param {[number, number][]} points
 * @param {import("@voip/core/flow_editor/geometry/nodes").FlowRect[]} obstacles
 * @returns {boolean}
 */
function collides(points, obstacles) {
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
 * Count genuine 90° corners, the same way `polylineToRoundedPath` does.
 *
 * @param {[number, number][]} points
 * @returns {number}
 */
function bendCount(points) {
    let bends = 0;
    for (let index = 1; index < points.length - 1; index++) {
        const [x0, y0] = points[index - 1];
        const [x1, y1] = points[index];
        const [x2, y2] = points[index + 1];
        const incomingX = x1 - x0;
        const incomingY = y1 - y0;
        const outgoingX = x2 - x1;
        const outgoingY = y2 - y1;
        if ((incomingX === 0 && outgoingY === 0) || (incomingY === 0 && outgoingX === 0)) {
            bends++;
        }
    }
    return bends;
}

describe("buildOrthogonalPath", () => {
    test("connects two ports on the same row with a straight line", () => {
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 0 },
        });
        expect(bendCount(points)).toBe(0);
        expect(hasReversal(points)).toBe(false);
    });

    test("connects two offset ports with a single elbow", () => {
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 150 },
        });
        expect(bendCount(points)).toBe(2);
        expect(hasReversal(points)).toBe(false);
    });

    test("routes around an obstacle directly between aligned ports", () => {
        const obstacles = [{ x1: 100, y1: -20, x2: 200, y2: 20 }];
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 0 },
            obstacles,
        });
        expect(collides(points, obstacles)).toBe(false);
        expect(hasReversal(points)).toBe(false);
    });

    test("never doubles back when an obstacle's expanded edge extends past the target", () => {
        // Reproduces the original bug: a naive detour computed only from the
        // obstacle's own edge, with no clamp against the target, used to
        // overshoot past `end` and have to travel back to reach it.
        const obstacles = [{ x1: 50, y1: 150, x2: 500, y2: 250 }];
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 100 },
            end: { x: 100, y: 400 },
            obstacles,
        });
        expect(collides(points, obstacles)).toBe(false);
        expect(hasReversal(points)).toBe(false);
    });

    test("clears an obstacle blocking both elbow shapes by widening to a corridor", () => {
        const obstacles = [{ x1: 100, y1: -10, x2: 200, y2: 210 }];
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 200 },
            obstacles,
        });
        expect(collides(points, obstacles)).toBe(false);
        expect(hasReversal(points)).toBe(false);
    });

    test("goes around two stacked obstacles that leave no gap", () => {
        const obstacles = [
            { x1: 100, y1: -100, x2: 200, y2: 50 },
            { x1: 100, y1: 50, x2: 200, y2: 200 },
        ];
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 0 },
            obstacles,
        });
        expect(collides(points, obstacles)).toBe(false);
        expect(hasReversal(points)).toBe(false);
        expect(bendCount(points)).toBe(4);
    });

    test("threads the gap between two stacked obstacles instead of going all the way around", () => {
        const obstacles = [
            { x1: 100, y1: -10, x2: 200, y2: 10 }, // blocks the direct row (y=0)
            { x1: 100, y1: 20, x2: 200, y2: 100 }, // gap between the two obstacles: y in (10, 20)
        ];
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 0 },
            obstacles,
        });
        expect(collides(points, obstacles)).toBe(false);
        expect(hasReversal(points)).toBe(false);
        const rowY = points.find(([, y]) => y !== 0)?.[1];
        expect(rowY).toBeWithin(10, 20);
    });

    test("shrinks the lead stub when an obstacle sits within its reach of the port", () => {
        const obstacles = [{ x1: 10, y1: -50, x2: 60, y2: 50 }];
        const { points } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 100 },
            obstacles,
            lead: 32,
        });
        expect(collides(points, obstacles)).toBe(false);
        expect(hasReversal(points)).toBe(false);
        // the shrunk lead never reaches as far as the obstacle's edge
        expect(points[1][0]).toBeLessThan(10);
    });

    test("routes a target behind the source without reversing, even with no obstacles", () => {
        // Ports always exit/enter horizontally to the right, so a target
        // positioned behind the source can never be reached with a single
        // elbow — only a row corridor can connect them without reversing.
        const { points } = buildOrthogonalPath({
            start: { x: 300, y: 0 },
            end: { x: 0, y: 100 },
        });
        expect(collides(points, [])).toBe(false);
        expect(hasReversal(points)).toBe(false);
        expect(bendCount(points)).toBe(4);
    });

    test("routes a target behind the source on the exact same row without reversing", () => {
        const { points } = buildOrthogonalPath({
            start: { x: 300, y: 100 },
            end: { x: 0, y: 100 },
        });
        expect(collides(points, [])).toBe(false);
        expect(hasReversal(points)).toBe(false);
        expect(bendCount(points)).toBe(4);
    });

    test("ignores an unrelated obstacle that never overlaps its own horizontal span", () => {
        // Reproduces a reported bug: dragging a node far from an unrelated
        // connection (e.g. moving "Start" while "Call a Group" -> "Hangup"
        // is elsewhere on the canvas) used to reshuffle that connection's
        // corridor row, because every obstacle's edges fed the row search
        // regardless of whether they were anywhere near the connection.
        const start = { x: 300, y: 100 };
        const end = { x: 0, y: 400 };
        const farAwayObstacleAt = (y) => [{ x1: -600, y1: y, x2: -500, y2: y + 100 }];
        const above = buildOrthogonalPath({ start, end, obstacles: farAwayObstacleAt(-800) });
        const below = buildOrthogonalPath({ start, end, obstacles: farAwayObstacleAt(800) });
        expect(collides(above.points, farAwayObstacleAt(-800))).toBe(false);
        expect(collides(below.points, farAwayObstacleAt(800))).toBe(false);
        expect(above.points).toEqual(below.points);
    });

    test("never crashes when start and end are the same point", () => {
        const { points } = buildOrthogonalPath({
            start: { x: 50, y: 50 },
            end: { x: 50, y: 50 },
        });
        expect(points.length).toBeGreaterThan(0);
    });

    test("every rounded corner in the path matches a genuine bend, never an unrounded reversal", () => {
        const obstacles = [
            { x1: 100, y1: -100, x2: 200, y2: 50 },
            { x1: 100, y1: 50, x2: 200, y2: 200 },
        ];
        const { points, path } = buildOrthogonalPath({
            start: { x: 0, y: 0 },
            end: { x: 300, y: 0 },
            obstacles,
        });
        const roundedCorners = path.match(/Q /g)?.length ?? 0;
        expect(roundedCorners).toBe(bendCount(points));
    });
});

describe("staircaseRoute", () => {
    test("terminates and stays collision-free even when a column is sandwiched by two obstacles", () => {
        // Two obstacles sandwich the source's own lead column (x=32) above and
        // below, while leaving row 0 itself clear so the lead stays exactly on
        // that column. Direct 0/2-bend shapes are impossible here (this is
        // only meant to exercise the escape valve in isolation).
        const obstacles = [
            { x1: 20, y1: 10, x2: 44, y2: 1000 },
            { x1: 20, y1: -1000, x2: 44, y2: -10 },
        ];
        const A = [32, 0];
        const B = [-268, 0];
        const points = staircaseRoute(A, B, obstacles);
        expect(collides(points, obstacles)).toBe(false);
        // every segment stays axis-aligned (no diagonal jump), even in the
        // guard-exhausted last-resort branch
        for (let index = 0; index < points.length - 1; index++) {
            const [x0, y0] = points[index];
            const [x1, y1] = points[index + 1];
            expect(x0 === x1 || y0 === y1).toBe(true);
        }
    });
});
