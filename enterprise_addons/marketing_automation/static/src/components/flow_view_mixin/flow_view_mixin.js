import { proxy, signal, useEffect, onMounted, onPatched } from "@odoo/owl";

/**
 * @param {Class} T
 * @returns {Class}
 */
export const FlowViewMixin = (T) =>
    class FlowViewMixin extends T {
        setup() {
            super.setup();
            this.editor = signal(null);
            this.state = proxy({
                origin: { x: 0, y: 0 },
                scale: 1,
                dragging: false,
                ready: false,
                visible: false,
            });

            useEffect(() => {
                const dragzone = this.editor();
                if (!dragzone) {
                    return;
                }
                /**
                 * @param {double} x1
                 * @param {double} y1
                 */
                const startDragging = (x1, y1) => {
                    /** @param {Event} event */
                    const dragging = (event) => {
                        const bounds = dragzone.getBoundingClientRect();
                        const x = event.clientX - bounds.left;
                        const y = event.clientY - bounds.top;
                        const { x: x2, y: y2 } = this.untransform(x, y);
                        const origin = this.transform(x2 - x1, y2 - y1);
                        this.state.origin.x = origin.x;
                        this.state.origin.y = origin.y;
                    };

                    /** @param {Event} event */
                    const stopDragging = (event) => {
                        this.state.dragging = false;
                        dragzone.removeEventListener("pointermove", dragging);
                        dragzone.removeEventListener("pointerleave", stopDragging);
                        dragzone.removeEventListener("pointerup", stopDragging);
                        addDragListeners();
                    };

                    dragzone.addEventListener("pointermove", dragging);
                    dragzone.addEventListener("pointerleave", stopDragging);
                    dragzone.addEventListener("pointerup", stopDragging);
                };

                const addDragListeners = () => {
                    /** @param {Event} event */
                    const onPointerDown = (event) => {
                        this.state.dragging = true;
                        const bounds = dragzone.getBoundingClientRect();
                        const x = event.clientX - bounds.left;
                        const y = event.clientY - bounds.top;
                        const pt = this.untransform(x, y);
                        startDragging(pt.x, pt.y);
                    };
                    dragzone.addEventListener("pointerdown", onPointerDown, { once: true });
                };

                /** @param {Event} event */
                const onMouseWheel = (event) => {
                    if (event.ctrlKey) {
                        event.preventDefault();
                        const ratio = 0.002 * event.deltaY;
                        const scale = (1 - ratio) * this.state.scale;
                        const bounds = dragzone.getBoundingClientRect();
                        const x = event.clientX - bounds.left;
                        const y = event.clientY - bounds.top;
                        this.zoomAt(x, y, scale);
                        return;
                    }
                    this.state.origin.y -= event.deltaY * 0.1;
                };

                /** @param {Event} */
                const onKeyDown = (event) => {
                    if (!event.target.contains(dragzone)) {
                        return;
                    }
                    const speed = 5;
                    if (event.key === "ArrowRight") {
                        this.state.origin.x += speed;
                    } else if (event.key === "ArrowDown") {
                        this.state.origin.y += speed;
                    } else if (event.key === "ArrowLeft") {
                        this.state.origin.x -= speed;
                    } else if (event.key === "ArrowUp") {
                        this.state.origin.y -= speed;
                    } else if (event.key === " ") {
                        this.fitGraphToView();
                    } else if (event.key === "+") {
                        this.zoomIn();
                    } else if (event.key === "-") {
                        this.zoomOut();
                    }
                };

                dragzone.addEventListener("wheel", onMouseWheel, { passive: false });
                document.addEventListener("keydown", onKeyDown);
                addDragListeners();

                return () => {
                    // cleanup
                    document.removeEventListener("keydown", onKeyDown);
                };
            });

            onMounted(() => {
                this.fitGraphToView();
                this.state.ready = true;
            });

            onPatched(() => {
                if (!this.state.ready) {
                    this.fitGraphToView();
                    this.state.ready = true;
                }
            });
        }

        /**
         * @param {Event} e1
         * @param {function} [onClick]
         * @param {function} [onDrag]
         * @param {function} [onDrop]
         */
        addPointerListeners(e1, onClick, onDrag, onDrop) {
            e1.preventDefault();

            const dragzone = this.editor();
            let hasDragged = false;

            /** @param {Event} e2 */
            const onDragMove = (e2) => {
                e2.preventDefault();
                const dx = e2.clientX - e1.clientX;
                const dy = e2.clientY - e1.clientY;
                const distance = Math.hypot(dx, dy);
                if (hasDragged || distance > 3) {
                    hasDragged = true;
                    onDrag?.(e2);
                }
            };

            /** @param {Event} e2 */
            const onDragEnd = (e2) => {
                e2.preventDefault();
                dragzone.removeEventListener("pointermove", onDragMove);
                dragzone.removeEventListener("pointerleave", onDragEnd);
                dragzone.removeEventListener("pointerup", onDragEnd);
                if (!hasDragged) {
                    onClick?.(e2);
                } else {
                    onDrop?.(e2);
                }
            };

            dragzone.addEventListener("pointermove", onDragMove);
            dragzone.addEventListener("pointerleave", onDragEnd);
            dragzone.addEventListener("pointerup", onDragEnd);
        }

        /**
         * Transforms the point (x, y) from the coordinate system of the editor
         * to the coordinate system of the screen.
         * @param {double} x
         * @param {double} y
         * @returns {Object}
         */
        transform(x, y) {
            const { scale, origin } = this.state;
            return {
                x: scale * x + origin.x,
                y: scale * y + origin.y,
            };
        }

        /**
         * Transforms the point (x, y) from the coordinate system of the screen
         * to the coordinate system of the editor.
         * @param {double} x
         * @param {double} y
         * @returns {Object}
         */
        untransform(x, y) {
            const { scale, origin } = this.state;
            return {
                x: (x - origin.x) / scale,
                y: (y - origin.y) / scale,
            };
        }

        /**
         * @param {double} x
         * @param {double} y
         * @returns {string}
         */
        getCSSTransform(x, y) {
            return `transform: translate(${x}px, ${y}px) scale(${this.state.scale}) translate(-50%, -50%)`;
        }

        /**
         * Zooms to a specific level at the given screen coordinates.
         * @param {double} x
         * @param {double} y
         * @param {double} scale
         */
        zoomAt(x, y, scale) {
            scale = Math.max(0.25, Math.min(scale, 4));
            const dx = (x - this.state.origin.x) * (1 - scale / this.state.scale);
            const dy = (y - this.state.origin.y) * (1 - scale / this.state.scale);
            this.state.scale = scale;
            this.state.origin.x += dx;
            this.state.origin.y += dy;
        }

        /** @param {double} scale */
        zoom(scale) {
            const bounds = this.editor().getBoundingClientRect();
            const x = bounds.width / 2;
            const y = bounds.height / 2;
            this.zoomAt(x, y, scale);
        }

        zoomIn() {
            this.zoom(this.state.scale + 0.1);
        }

        zoomOut() {
            this.zoom(this.state.scale - 0.1);
        }

        /**
         * Reframes the graph so that it is centered on screen.
         */
        fitGraphToView() {
            const editor = this.editor();
            if (!editor) {
                return;
            }
            const elements = editor.querySelectorAll(".o-editor-node, .o-editor-flag");
            if (!elements.length) {
                return;
            }

            // Get bounding box in screen space
            let minX = Infinity,
                minY = Infinity,
                maxX = -Infinity,
                maxY = -Infinity;
            elements.forEach((element) => {
                const bounds = element.getBoundingClientRect();
                minX = Math.min(minX, bounds.left);
                minY = Math.min(minY, bounds.top);
                maxX = Math.max(maxX, bounds.right);
                maxY = Math.max(maxY, bounds.bottom);
            });

            // Convert to editor space:
            const bounds = editor.getBoundingClientRect();
            const { x: x1, y: y1 } = this.untransform(minX - bounds.left, minY - bounds.top);
            const { x: x2, y: y2 } = this.untransform(maxX - bounds.left, maxY - bounds.top);
            const dw = x2 - x1;
            const dh = y2 - y1;

            // Apply scale and center, clear of the editor edges:
            const FIT_MARGIN = 48;
            const width = editor.offsetWidth - 2 * FIT_MARGIN;
            const height = editor.offsetHeight - 2 * FIT_MARGIN;
            const scale = Math.max(0.25, Math.min(1, width / dw, height / dh));

            this.state.scale = scale;
            this.state.origin.x = (editor.offsetWidth - scale * dw) / 2 - x1 * scale;
            this.state.origin.y = (editor.offsetHeight - scale * dh) / 2 - y1 * scale;
        }

        /**
         * @param {{ x: double, y: double }} a - Starting point
         * @param {{ x: double, y: double }} b - End point
         * @param {double} t (between 0 and 1)
         * @returns {{ x: double, y: double }}
         */
        getBezierPoint(a, b, t) {
            const u = 1 - t;
            const uu = u * u;
            const uuu = uu * u;
            const tt = t * t;
            const ttt = tt * t;
            const midX = (a.x + b.x) / 2;
            // P0 = (a.x, a.y)
            // P1 = (midX, a.y)
            // P2 = (midX, b.y)
            // P3 = (b.x, b.y)
            return {
                x: uuu * a.x + 3 * uu * t * midX + 3 * u * tt * midX + ttt * b.x,
                y: uuu * a.y + 3 * uu * t * a.y + 3 * u * tt * b.y + ttt * b.y,
            };
        }
    };
