import { setRecurringAnimationFrame, debounce } from "@web/core/utils/timing";
import { renderToElement } from "@web/core/utils/render";
import { cookie } from "@web/core/browser/cookie";
import { session } from "@web/session";
const MIN_ID = -(2 ** 30);

// Sign item types whose font size scales with the page rather than with
// their own height.
const LARGER_SIGN_ITEM_TYPES = ["signature", "initial", "textarea", "selection", "stamp"];

/**
 * Computes the font size of a sign item, based on its type and dimensions.
 *
 * @param {String} type - the sign item type
 * @param {Number} itemHeight - the item's inner height, in pixels
 * @param {Number} pageHeight - the page height, in pixels
 * @returns {Number} the font size, in pixels
 */
export function getSignItemFontSize(type, itemHeight, pageHeight) {
    return (LARGER_SIGN_ITEM_TYPES.includes(type) ? pageHeight * 0.015 : itemHeight) * 0.8;
}

/**
 * Adds helper lines to the document
 *
 * @param {HTMLElement} target
 * @returns {Object} helpers
 * @returns {Function} helpers.show shows the helper lines at a certain sign item
 * @returns {Function} helpers.hide hides the helper lines
 */
export function startHelperLines(target) {
    function showHelperLinesAt(signItem, coords) {
        const calculate = {
            left: (pos) => ({ left: `${pos.left}px` }),
            right: (pos) => ({ left: `${pos.left + pos.width}px` }),
            top: (pos) => ({ top: `${pos.top}px` }),
            bottom: (pos) => ({ top: `${pos.top + pos.height}px` }),
        };

        const rect = signItem.getBoundingClientRect();
        const positions = {
            top: (coords && coords.y) || rect.top,
            left: (coords && coords.x) || rect.left,
            height: rect.height,
            width: rect.width,
        };
        for (const line in helperLines) {
            const newPos = calculate[line](positions);
            Object.assign(helperLines[line].style, {
                visibility: "visible",
                ...newPos,
            });
        }
    }

    function hideHelperLines() {
        for (const line in helperLines) {
            helperLines[line].style.visibility = "hidden";
        }
    }

    const top = target.createElement("div");
    const bottom = target.createElement("div");
    top.className = "o_sign_drag_helper o_sign_drag_top_helper";
    bottom.className = "o_sign_drag_helper o_sign_drag_top_helper";
    const left = target.createElement("div");
    const right = target.createElement("div");
    left.className = "o_sign_drag_helper o_sign_drag_side_helper";
    right.className = "o_sign_drag_helper o_sign_drag_side_helper";

    const body = target.querySelector("body");
    body.appendChild(top);
    body.appendChild(bottom);
    body.appendChild(left);
    body.appendChild(right);

    const helperLines = {
        top,
        bottom,
        left,
        right,
    };

    return {
        show: showHelperLinesAt,
        hide: hideHelperLines,
    };
}

export function isVisible(e) {
    return e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
}

export function offset(el) {
    const box = el.getBoundingClientRect();
    const docElem = document.documentElement;
    return {
        top: box.top + window.scrollY - docElem.clientTop,
        left: box.left + window.scrollY - docElem.clientLeft,
    };
}

/**
 * Normalizes the normalize position of a sign item to prevent dropping outside the page
 * @param {Number} position x/y position
 * @param {Number} itemDimension size of item at x/y direction
 * @returns {Number}
 */
export function normalizePosition(position, itemDimension) {
    if (position < 0) {
        return 0;
    } else if (position + itemDimension > 1.0) {
        return 1.0 - itemDimension;
    }
    return position;
}

/**
 * Normalizes the new dimension of a sign item to prevent it from resizing outside the page
 * @param {Number} dimension
 * @param {Number} position
 * @returns {Number} normalized dimension
 */
export function normalizeDimension(dimension, position) {
    if (position + dimension > 1) {
        return 1 - position;
    }
    return dimension;
}

/**
 * Generates a random negative ID to be added to sign items that were just created and are not in the DB yet
 * @returns {Number}
 */
export function generateRandomId() {
    return Math.floor(Math.random() * MIN_ID) - 1;
}

/**
 * Calculates the offset of the pointer coordinates relative to the iframe container.
 *
 * @param {HTMLElement} iframeContainer - The iframe container element.
 * @param {number} x - The x-coordinate of the pointer (relative to the window).
 * @param {number} y - The y-coordinate of the pointer (relative to the window).
 * @returns {{ x: number, y: number }} The coordinates adjusted relative to the iframe container.
*/
export function getOffsetFromIframe(iframeContainer, x, y) {
    // The rect starts at the container's border box, while the iframe starts
    // at its padding box. Skip the container's borders to align their origins.
    const iframeContainerRec = iframeContainer.getBoundingClientRect();
    const offset = {
        x: x - iframeContainerRec.left - iframeContainer.clientLeft,
        y: y - iframeContainerRec.top - iframeContainer.clientTop
    };

    return offset;
}

/**
 * Returns the viewer container element inside the given iframe.
 *
 * @param {HTMLIFrameElement} iframe - The iframe element to search within.
 * @returns {HTMLElement|null} The viewer container element, or null if not found.
*/
export function getIframeViewerContainer (iframe) {
    return iframe.root.querySelector("#viewerContainer");
}

/**
 * Returns the main iframe container element in the document.
 *
 * @returns {HTMLElement|null} The iframe container element, or null if not found.
 */
export function getIframeContainer() {
    return document.querySelector(".o_sign_documents_container");
}

/**
 * Performs a single edge-scroll step on a scrollable container,
 * based on the pointer position relative to its edges.
 *
 * @param {HTMLElement} container - The scrollable container element.
 * @param {{x: number, y: number}} pointerOffset - Pointer position relative to the container.
 *   - `x`: Horizontal offset in pixels.
 *   - `y`: Vertical offset in pixels.
 * @param {Object} [options] - Optional configuration.
 * @param {number} [options.boundary=0.2] - Fraction (0–1) of the container’s size
 *   near each edge used as the scroll activation zone.
 * @param {number} [options.maxDragAmount=40] - Maximum pixels to scroll per animation frame.
 *
 * @returns {boolean} - Returns `true` if scrolling occurred, otherwise `false`.
*/
export function edgeScrollStep(
    container,
    pointerOffset,
    { boundary = 0.2, maxDragAmount = 40, maxBoundary = Infinity } = {} // defaults
) {
    let scrollX = 0, scrollY = 0;

    // Activation boundaries, optionally capped in pixels so that
    // they stay reasonable on small containers (e.g. phone screens).
    const leftBoundary = Math.min(container.clientWidth * boundary, maxBoundary);
    const rightBoundary = container.clientWidth - leftBoundary;
    const topBoundary = Math.min(container.clientHeight * boundary, maxBoundary);
    const bottomBoundary = container.clientHeight - topBoundary;

    // Horizontal
    if (pointerOffset.x <= leftBoundary) {
        const intensity = 1 - pointerOffset.x / leftBoundary;
        scrollX = -(intensity * maxDragAmount); // left
    } else if (pointerOffset.x >= rightBoundary) {
        const intensity = (pointerOffset.x - rightBoundary) / (container.clientWidth - rightBoundary);
        scrollX = intensity * maxDragAmount; // right
    }

    // Vertical
    if (pointerOffset.y <= topBoundary) {
        const intensity = 1 - pointerOffset.y / topBoundary;
        scrollY = -(intensity * maxDragAmount); // up
    } else if (pointerOffset.y >= bottomBoundary) {
        const intensity = (pointerOffset.y - bottomBoundary) / (container.clientHeight - bottomBoundary);
        scrollY = intensity * maxDragAmount; // down
    }

    if (scrollX !== 0 || scrollY !== 0) {
        container.scrollBy(scrollX, scrollY);
        return true; // continue loop (for recurring animation)
    }
    return false; // stop loop (for recurring animation)
}

/**
 * Starts a recurring animation loop that continuously performs
 * edge scrolling while the pointer remains near the container edges.
 *
 * @param {HTMLElement} container - The scrollable container element.
 * @param {{x: number, y: number}} pointerOffset - Pointer position relative to the container.
 * @param {Object} [options] - Optional configuration.
 * @param {number} [options.boundary=0.2] - Fraction (0–1) of the container’s size
 *   near each edge used as the scroll activation zone.
 * @param {number} [options.maxDragAmount=40] - Maximum pixels to scroll per animation frame.
 *
 * @returns {Function} - A function that stops the scrolling loop when called.
*/
export function startEdgeScroll(container, pointerOffset, options) {
    const step = () => edgeScrollStep(container, pointerOffset, options);
    const stopScroll = setRecurringAnimationFrame(step);
    return stopScroll;
}

/**
 * Adds resizing functionality to a sign item
 * @param {SignItem} signItem
 * @param {Function} onResize
 */
export function startResize(iframe, signItem, onResize) {
    const viewerContainer = getIframeViewerContainer(iframe);
    const pointer = {};
    const resizeHandleWidth = signItem.el.querySelector(".resize_width");
    const resizeHandleHeight = signItem.el.querySelector(".resize_height");
    const resizeHandleBoth = signItem.el.querySelector(".resize_both");

    const computeDimensions = (e) => {
        const { direction, x, y } = pointer;
        const computedStyle = getComputedStyle(signItem.el);
        const signItemAbsoluteWidth = parseInt(computedStyle.width);
        const signItemAbsoluteHeight = parseInt(computedStyle.height);
        const dX = e.clientX - x;
        const dY = e.clientY - y;

        Object.assign(pointer, {
            x: e.clientX,
            y: e.clientY,
        });

        const factor = {
            x: (dX + signItemAbsoluteWidth) / signItemAbsoluteWidth,
            y: (dY + signItemAbsoluteHeight) / signItemAbsoluteHeight,
        };

        if (dX < 0 && Math.abs(dX) >= signItemAbsoluteWidth) {
            factor.x = 1;
        }

        if (dY < 0 && Math.abs(dY) >= signItemAbsoluteHeight) {
            factor.y = 1;
        }

        const width =
            direction === "width" || direction === "both"
                ? Math.round(
                    normalizeDimension(factor.x * signItem.data.width, signItem.data.posX) * 1000
                ) / 1000
                : signItem.data.width;

        const height =
            direction === "height" || direction === "both"
                ? Math.round(
                    normalizeDimension(factor.y * signItem.data.height, signItem.data.posY) * 1000
                ) / 1000
                : signItem.data.height;

        return { height, width };
    };

    const handlePointerMove = (e) => {
        if (signItem.el.classList.contains("o_resizing")) {
            e.preventDefault();
            onResize(signItem, computeDimensions(e), false);
        }
    };

    const resizeEndingEvents = ["pointerup", "pointercancel", "pointerleave", "blur", "contextmenu"];
    const debouncedOnPointerMove = debounce(handlePointerMove, "animationFrame", true);
    const onResizingEnd = (e) => {
        if (signItem.el.classList.contains("o_resizing")) {
            e.preventDefault(); // Prevent extra touch actions on touchscreens to avoid interfering with resizing.
            onResize(signItem, computeDimensions(e), true);
            signItem.el.classList.remove("o_resizing");
            viewerContainer.removeEventListener("pointermove", debouncedOnPointerMove);
            resizeEndingEvents.forEach(eventType => viewerContainer.removeEventListener(eventType, onResizingEnd));
        }
    };
    const handlePointerDown = (e, direction) => {
        e.preventDefault();
        e.stopPropagation(); // Prevents touch screen gestures like scrolling or zooming.
        Object.assign(pointer, { x: e.clientX, y: e.clientY, direction });
        signItem.el.classList.add("o_resizing");
        viewerContainer.addEventListener("pointermove", debouncedOnPointerMove);

        // Call onResizingEnd on "pointerup", "pointercancel", "blur", and "contextmenu" events,
        // since the user might cancel or leave the container without a pointerup.
        // This ensures pointermove listeners are properly removed and don’t linger indefinitely.
        resizeEndingEvents.forEach(eventType => viewerContainer.addEventListener(eventType, onResizingEnd));
    };

    resizeHandleWidth.addEventListener("pointerdown", (e) => handlePointerDown(e, "width"), { passive: false });
    resizeHandleHeight.addEventListener("pointerdown", (e) => handlePointerDown(e, "height"), { passive: false });
    resizeHandleBoth.addEventListener("pointerdown", (e) => handlePointerDown(e, "both"), { passive: false });
}

/**
 * Generates the PDF.JS URL from the attachment location
 * @param { String } attachmentLocation
 * @returns
 */
export function buildPDFViewerURL(attachmentLocation) {
    const date = new Date().toISOString();
    const baseURL = "/web/static/lib/pdfjs/web/viewer.html";
    // encodes single quote and double quotes as encodeURIComponent does not handle those
    attachmentLocation = encodeURIComponent(attachmentLocation)
        .replace(/'/g, "%27")
        .replace(/"/g, "%22");
    return `${baseURL}?unique=${date}&file=${attachmentLocation}#page=1&pagemode=none`;
}

export function injectPDFCustomStyles(iframeDoc) {
    /* Apply custom styles for documents's PDF viewers as early as possible
    to minimize the visibility of default PDF.js styles during rendering. */
    const link = iframeDoc.createElement('link');
    link.rel = 'stylesheet';
    link.type = 'text/css';
    link.href = '/sign/static/src/css/pdfjs_overrides.css';
    iframeDoc.head.appendChild(link);
    // Sync Odoo's theme to the isolated PDF iframe to override PDF.js's native OS-level dark mode.
    // but keep it always light when we are in the protal since we have no themes there (always light)
    // Doing this during CSS injection prevents visual flickering when the viewer loads.
    const isFrontend = session.is_frontend;
    const isDarkTheme = !isFrontend && cookie.get("color_scheme") === "dark";
    const iframeRoot = iframeDoc.documentElement;
    if (isDarkTheme) {
        iframeRoot.classList.add('is-dark');
        iframeRoot.classList.remove('is-light');
        iframeRoot.style.colorScheme = 'dark';
    } else {
        iframeRoot.classList.add('is-light');
        iframeRoot.classList.remove('is-dark');
        iframeRoot.style.colorScheme = 'light';
    }
}

/**
 * Returns helper functions for drag-and-drop.
 *
 * Includes:
 * - clone: create a copy of an element
 * - style: apply styles to a dragged element
 * - insert: place the element into the DOM
 * - removeClone: remove the temporary clone
 *
 * @returns {Object} drag-and-drop helpers
*/
export function draggingHelperFunctions() {
    let element;
    let copy;

    /**
     * Clones the given element and saves it as a temporary variable.
     *
     * @param {HTMLElement} _element - The element to clone.
    */
    function clone(_element) {
        element = _element;
        copy = element.cloneNode(true);
    }

    /**
     * Applies styling to dragged sign item buttons.
     *
     * @param {HTMLElement} _element - The sign field button element.
     * @param {HTMLIFrameElement} iframe - The pdf iframe.
     * @param {Function} addStyle - Callback function to add styles to elements.
     * @param {Function} addClass - Callback function to add classes to elements.
     * @param {Function} removeStyle - Callback function to remove styles from elements.
    */
    function styleSignItemButtons(_element, iframe, addStyle, addClass, removeStyle) {
        const itemTypeId = element.dataset.itemTypeId;
        const type = iframe.signItemTypesById[itemTypeId];

        // Find the first visible page on the screen, as its text layer will be loaded.
        // (The iframe uses lazy loading, so visible pages are fully rendered.)
        const pages = iframe.root.querySelectorAll('.page');
        const firstVisiblePage = Array.from(pages).find(page => {
            const rect = page.getBoundingClientRect();
            return rect.bottom > 0 && rect.top < window.innerHeight;
        });
        if (!firstVisiblePage) return;

        const pageRect = (firstVisiblePage.querySelector('.textLayer') || firstVisiblePage).getBoundingClientRect();
        const newWidth = type.default_width * pageRect.width;
        const newHeight = type.default_height * pageRect.height;

        // Resize the dragged element to be relative to the dimensions of the
        // page, and show the sign item as it will be rendered once dropped instead of its content.
        // The original content is hidden by css, but not removed because on touch screens,
        // the pointer events are implicitly captured by the touchstart target
        // inside the button, and removing it would abort the drag.
        addClass(_element, "o_sign_dragging_item")
        removeStyle(_element, "maxWidth", "maxHeight", "minWidth", "minHeight");
        addStyle(_element, {
            "--sign-item-width": `${newWidth}px`,
            "--sign-item-height": `${newHeight}px`,
            // The dropped item's clientHeight excludes its vertical borders.
            fontSize: `${getSignItemFontSize(type.item_type, newHeight - 2, pageRect.height)}px`,
        });
        _element.appendChild(
            renderToElement("sign.signItem", iframe.createSignItemDataFromType(element.dataset))
        );
    }

    /**
     * Inserts the cloned element at the position of the dragged element.
    */
    function insert() {
        if (element) {
            element.insertAdjacentElement("beforebegin", copy);
        }
    }

    /**
     * Removes the cloned element from the DOM, if it exists, along with the
     * sign item preview appended to the dragged element while dragging.
    */
    function removeClone() {
        element?.querySelector(":scope > .o_sign_sign_item")?.remove();
        if (copy) {
            copy.remove();
        }
        copy = null;
        element = null;
    }

    return { clone, style: styleSignItemButtons, insert, removeClone };
}
