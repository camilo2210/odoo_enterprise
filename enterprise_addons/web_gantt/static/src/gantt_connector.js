import { onWillRender, useLayoutEffect } from "@web/owl2/utils";
import { Component, useProps, signal, t } from "@odoo/owl";
import { rtl } from "./gantt_helpers";

/**
 * @typedef {"error" | "warning"} ConnectorAlert
 * @typedef {`__connector__${number | "new"}`} ConnectorId
 * @typedef {import("./gantt_renderer").Point} Point
 *
 * @typedef ConnectorProps
 * @property {ConnectorId} id
 * @property {ConnectorAlert | null} alert
 * @property {boolean} highlighted
 * @property {boolean} displayButtons
 * @property {Point | () => Point | null} sourcePoint
 * @property {Point | () => Point | null} targetPoint
 *
 * @typedef {Object} PathInfo
 * @property {Point} sourceControlPoint
 * @property {Point} targetControlPoint
 * @property {Point} removeButtonPosition
 *
 * @typedef Point
 * @property {number} [x]
 * @property {number} [y]
 */

/**
 * Gets the stroke's rgba css string corresponding to the provided parameters for both the stroke and its
 * hovered state.
 *
 * @param {number} r [0, 255]
 * @param {number} g [0, 255]
 * @param {number} b [0, 255]
 * @return {{ stroke: string, hoveredStroke: string }} the css colors.
 */
export function getStrokeAndHoveredStrokeColor(r, g, b) {
    const dr = Math.round(r * 0.9);
    const dg = Math.round(g * 0.9);
    const db = Math.round(b * 0.9);
    return {
        color: `rgba(${r},${g},${b},0.5)`,
        highlightedColor: `rgba(${r},${g},${b},1)`,
        hoveredHighlightedColor: `rgba(${dr},${dg},${db},1)`,
    };
}

export const COLORS = {
    default: getStrokeAndHoveredStrokeColor(143, 143, 143),
    error: getStrokeAndHoveredStrokeColor(211, 65, 59),
    warning: getStrokeAndHoveredStrokeColor(236, 151, 31),
    outline: getStrokeAndHoveredStrokeColor(255, 255, 255),
};

/** @extends {Component<{ reactive: ConnectorProps }, any>} */
export class GanttConnector extends Component {
    props = useProps({
        reactive: t.object({
            id: t.string(),
            alert: t.or([t.literal("error"), t.literal("warning"), t.literal(null)]).optional(),
            highlighted: t.boolean().optional(),
            displayButtons: t.boolean().optional(),
            sourcePoint: t.or([
                t.literal(null),
                t.function(),
                t.object({ left: t.number(), top: t.number() }),
            ]),
            targetPoint: t.or([
                t.literal(null),
                t.function(),
                t.object({ left: t.number(), top: t.number() }),
            ]),
            dashed: t.boolean().optional(),
        }),
        onRemoveButtonClick: t.function().optional(),
        onConnectorHover: t.function(),
    });
    static template = "web_gantt.GanttConnector";

    rootRef = signal.ref();
    style = {
        hoverEaseWidth: 10,
        stroke: { width: 2 },
        outlineStroke: { width: 1 },
        // Radius for rounded corners in connector paths. Affects curve smoothness between source and target points.
        cornerRadius: 8,
    };

    get alert() {
        return this.props.reactive.alert;
    }

    get displayButtons() {
        return this.props.reactive.displayButtons;
    }

    get highlighted() {
        return this.props.reactive.highlighted;
    }

    get id() {
        return this.props.reactive.id;
    }

    get isNew() {
        return this.id.endsWith("new");
    }

    get sourcePoint() {
        return this.props.reactive.sourcePoint;
    }

    get targetPoint() {
        return this.props.reactive.targetPoint;
    }

    get isDashed() {
        return this.props.reactive.dashed;
    }

    setup() {
        onWillRender(this.onWillRender);

        useLayoutEffect(
            (el, sourceLeft, sourceTop, targetLeft, targetTop) => {
                if (!el) {
                    return;
                }
                const { removeButtonPosition } = this.getRemoveButtonInfo(
                    { left: sourceLeft, top: sourceTop },
                    { left: targetLeft, top: targetTop }
                );

                const drawingCommands = this.createOrthogonalPath(
                    { left: sourceLeft, top: sourceTop },
                    { left: targetLeft, top: targetTop }
                );

                const paths = el.querySelectorAll(
                    ".o_connector_stroke, .o_connector_stroke_hover_ease"
                );
                for (const path of paths) {
                    path.setAttribute("d", drawingCommands);
                }

                const svgButtons = el.querySelector(".o_connector_stroke_buttons");
                if (svgButtons) {
                    svgButtons.setAttribute("x", removeButtonPosition.left - 24);
                    svgButtons.setAttribute("y", removeButtonPosition.top - 8);
                }
            },
            () => this.getEffectDependencies()
        );
    }

    getEffectDependencies() {
        let sourcePoint = this.sourcePoint || { left: 0, top: 0 };
        if (typeof sourcePoint === "function") {
            sourcePoint = sourcePoint();
        }
        let targetPoint = this.targetPoint || { left: 0, top: 0 };
        if (typeof targetPoint === "function") {
            targetPoint = targetPoint();
        }
        const { x, y } = this.rootRef()?.getBoundingClientRect() || { x: 0, y: 0 };

        return [
            this.rootRef(),
            sourcePoint.left - x,
            sourcePoint.top - y,
            targetPoint.left - x,
            targetPoint.top - y,
            this.displayButtons,
        ];
    }

    /**
     * Creates an orthogonal path with small curves at corners.
     *
     * @param {Point} sourcePoint
     * @param {Point} targetPoint
     * @returns {string} SVG path commands
     */
    createOrthogonalPath(sourcePoint, targetPoint) {
        const xDelta = targetPoint.left - sourcePoint.left;
        const yDelta = targetPoint.top - sourcePoint.top;

        // LTR: 1 (Right is forward). RTL: -1 (Left is forward).
        const flowDir = rtl() ? -1 : 1;

        const logicalXDelta = xDelta * flowDir;

        const dirY = Math.sign(yDelta) || 1;

        const curvedElbow = (start, corner, end) => [
            `L ${start.left},${start.top}`,
            `Q ${corner.left},${corner.top} ${end.left},${end.top}`,
        ];

        //=========================================
        // BACKWARD / WRAP-AROUND ROUTING
        //=========================================
        if (Math.abs(logicalXDelta) < this.style.cornerRadius || logicalXDelta < 0) {
            // Multipliers ensure wrap-around loops out to the correct sides
            const exitBuffer = 30 * flowDir;
            const wrapRadiusX = Math.min(this.style.cornerRadius, Math.abs(yDelta) / 2) * flowDir;
            const wrapRadiusY = Math.min(this.style.cornerRadius, Math.abs(yDelta) / 2) * dirY;

            const midY = sourcePoint.top + yDelta / 2;

            return [
                `M ${sourcePoint.left},${sourcePoint.top}`,

                ...curvedElbow(
                    { left: sourcePoint.left + exitBuffer - wrapRadiusX, top: sourcePoint.top },
                    { left: sourcePoint.left + exitBuffer, top: sourcePoint.top },
                    { left: sourcePoint.left + exitBuffer, top: sourcePoint.top + wrapRadiusY }
                ),

                ...curvedElbow(
                    { left: sourcePoint.left + exitBuffer, top: midY - wrapRadiusY },
                    { left: sourcePoint.left + exitBuffer, top: midY },
                    { left: sourcePoint.left + exitBuffer - wrapRadiusX, top: midY }
                ),

                ...curvedElbow(
                    { left: targetPoint.left - exitBuffer + wrapRadiusX, top: midY },
                    { left: targetPoint.left - exitBuffer, top: midY },
                    { left: targetPoint.left - exitBuffer, top: midY + wrapRadiusY }
                ),

                ...curvedElbow(
                    { left: targetPoint.left - exitBuffer, top: targetPoint.top - wrapRadiusY },
                    { left: targetPoint.left - exitBuffer, top: targetPoint.top },
                    { left: targetPoint.left - exitBuffer + wrapRadiusX, top: targetPoint.top }
                ),

                `L ${targetPoint.left},${targetPoint.top}`,
            ].join(" ");
        }

        //==========================================
        // STANDARD FORWARD ROUTING
        //==========================================
        const midX = sourcePoint.left + xDelta / 2;

        const radiusX = Math.min(this.style.cornerRadius, Math.abs(xDelta) / 2) * flowDir;
        const radiusY = Math.min(this.style.cornerRadius, Math.abs(yDelta) / 2) * dirY;

        return [
            `M ${sourcePoint.left},${sourcePoint.top}`,

            ...curvedElbow(
                { left: midX - radiusX, top: sourcePoint.top },
                { left: midX, top: sourcePoint.top },
                { left: midX, top: sourcePoint.top + radiusY }
            ),

            ...curvedElbow(
                { left: midX, top: targetPoint.top - radiusY },
                { left: midX, top: targetPoint.top },
                { left: midX + radiusX, top: targetPoint.top }
            ),

            `L ${targetPoint.left},${targetPoint.top}`,
        ].join(" ");
    }

    /**
     * Returns the control points and remove button position for connector path.
     *
     * @param {Point} sourcePoint
     * @param {Point} targetPoint
     * @returns {PathInfo}
     */
    getRemoveButtonInfo(sourcePoint, targetPoint) {
        const xDelta = targetPoint.left - sourcePoint.left;
        const yDelta = targetPoint.top - sourcePoint.top;

        const cornerX = sourcePoint.left + xDelta / 2;
        const cornerY = sourcePoint.top + yDelta / 2;

        return {
            sourceControlPoint: { left: cornerX, top: sourcePoint.top },
            targetControlPoint: { left: cornerX, top: targetPoint.top },
            removeButtonPosition: { left: cornerX, top: cornerY },
        };
    }

    //-------------------------------------------------------------------------
    // Handlers
    //-------------------------------------------------------------------------

    onRemoveButtonClick() {
        if (this.props.onRemoveButtonClick) {
            this.props.onRemoveButtonClick();
        }
    }

    onWillRender() {
        const key = this.highlighted ? "highlightedColor" : "color";
        this.style.outlineStroke.color = COLORS.outline[key];
        if (this.props.onConnectorHover() && this.highlighted) {
            this.style.stroke.color = COLORS[this.alert || "default"].hoveredHighlightedColor;
        } else {
            this.style.stroke.color = COLORS[this.alert || "default"][key];
        }
    }
}
