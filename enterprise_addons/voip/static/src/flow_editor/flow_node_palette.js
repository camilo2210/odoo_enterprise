import { Component, proxy, t, useListener, useProps } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";

const DRAG_THRESHOLD = 6;

export class FlowNodePalette extends Component {
    static template = "voip.FlowNodePalette";
    static components = { Dropdown, DropdownItem };

    props = useProps({
        nodes: t.array(),
        onDrop: t.function(),
        onSelect: t.function(),
        readonly: t.boolean(),
        registry: t.any(),
    });

    setup() {
        this.state = proxy({
            draggingType: null,
            isDragging: false,
            overCanvas: false,
            pointerX: 0,
            pointerY: 0,
        });
        useListener(window, "pointermove", this.onPointerMove.bind(this));
        useListener(window, "pointerup", this.onPointerUp.bind(this));
        useListener(window, "pointercancel", this.cancelDrag.bind(this));
    }

    get title() {
        return _t("Add a node");
    }

    get addNodeLabel() {
        return _t("Add node");
    }

    get unavailableLabel() {
        return _t("Already added");
    }

    get items() {
        const definitions = this.props.registry.getAll();
        return this.props.registry
            .getCategories()
            .flatMap((category) =>
                definitions.filter(
                    (definition) => definition.palette && definition.category === category.id
                )
            )
            .map((definition) => ({
                ...definition,
                available: this.props.registry.canCreate(definition.type, this.props.nodes),
            }));
    }

    get ghost() {
        if (!this.state.isDragging) {
            return null;
        }
        const definition = this.props.registry.get(this.state.draggingType);
        return {
            ...definition,
            style: `left: ${this.state.pointerX - definition.size.width / 2}px; top: ${
                this.state.pointerY - definition.size.height / 2
            }px; width: ${definition.size.width}px; height: ${definition.size.height}px;`,
        };
    }

    /**
     * @param {string} type
     * @param {PointerEvent} ev
     */
    onPointerDown(type, ev) {
        if (ev.button !== 0 || !this.props.registry.canCreate(type, this.props.nodes)) {
            return;
        }
        ev.preventDefault();
        this.activePointerId = ev.pointerId;
        this.pointerDownPosition = { x: ev.clientX, y: ev.clientY };
        Object.assign(this.state, {
            draggingType: type,
            isDragging: false,
            pointerX: ev.clientX,
            pointerY: ev.clientY,
        });
    }

    /**
     * @param {PointerEvent} ev
     */
    onPointerMove(ev) {
        if (ev.pointerId !== this.activePointerId || !this.state.draggingType) {
            return;
        }
        ev.preventDefault();
        const isDragging =
            this.state.isDragging ||
            Math.hypot(
                ev.clientX - this.pointerDownPosition.x,
                ev.clientY - this.pointerDownPosition.y
            ) >= DRAG_THRESHOLD;
        Object.assign(this.state, {
            isDragging,
            pointerX: ev.clientX,
            pointerY: ev.clientY,
            overCanvas:
                isDragging &&
                Boolean(
                    document.elementFromPoint(ev.clientX, ev.clientY)?.closest(".o_flow_editor")
                ),
        });
    }

    /**
     * @param {PointerEvent} ev
     */
    onPointerUp(ev) {
        if (ev.pointerId !== this.activePointerId || !this.state.draggingType) {
            return;
        }
        const canvasEl = document
            .elementFromPoint(ev.clientX, ev.clientY)
            ?.closest(".o_flow_editor");
        try {
            if (!this.state.isDragging) {
                this.props.onSelect(this.state.draggingType);
            } else if (canvasEl) {
                this.props.onDrop({
                    type: this.state.draggingType,
                    clientX: ev.clientX,
                    clientY: ev.clientY,
                    canvasRect: canvasEl.getBoundingClientRect(),
                });
            }
        } finally {
            this.cancelDrag();
        }
    }

    cancelDrag() {
        this.activePointerId = null;
        this.pointerDownPosition = null;
        Object.assign(this.state, {
            draggingType: null,
            isDragging: false,
            overCanvas: false,
        });
    }
}
