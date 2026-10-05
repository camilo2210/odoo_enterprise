/** @odoo-module **/

/**
 * Triggers a synthetic PointerEvent on the given element.
 * Used to simulate pointer-based interactions such as dragging or clicking
 * when testing or automating UI behavior.
 *
 * @param {Element} element - The target element to dispatch the event on.
 * @param {string} type - The type of event (e.g. "pointerdown", "pointermove", "pointerup").
 * @param {Object} [data={}] - Optional event data, such as coordinates or custom properties.
*/
function triggerPointerEvent(element, type, data = {}) {
    // Create a new pointer event with default and user-specified options
    const event = new PointerEvent(type, {
        bubbles: true,        // allow the event to bubble up through the DOM
        cancelable: true,     // allow event.preventDefault() to be called
        pointerId: 1,         // arbitrary pointer ID (1 = mouse)
        pointerType: 'mouse', // simulate a mouse-based pointer
        clientX: data.clientX || 0, // X position relative to the viewport
        clientY: data.clientY || 0, // Y position relative to the viewport
        ...data,              // allow overriding or adding custom event fields
    });

    // Dispatch the event to the target element
    element.dispatchEvent(event);
}

/**
 * Waits until the next browser animation frame before continuing execution.
 *
 * This is useful when simulating user interactions (like drag-and-drop)
 * to ensure that the DOM and rendering have updated between steps.
 * It returns a Promise that resolves on the next repaint cycle.
 *
 * @returns {Promise<void>} Resolves when the next animation frame occurs.
*/
function waitNextFrame() {
    return new Promise(resolve => requestAnimationFrame(resolve));
}

/**
 * Simulates dragging a signature item from one element to another inside an iframe
 * using PointerEvents. The drag moves smoothly across multiple animation frames
 * to ensure Odoo tour detects the interaction correctly.
 *
 * @param {Element} from - The source element to start dragging from.
 * @param {Element} to - The destination element to drop onto (page).
 * @param {number} [height=0.5] - Vertical position (0–1) within the elements to start/drop.
 * @param {number} [width=0.5] - Horizontal position (0–1) within the elements to start/drop.
 * @param {number} [steps=1] - Number of intermediate drag movements between the start and end positions.
 */
async function dragAndDropSignItemAtHeight(from, to, height = 0.5, width = 0.5, steps=1) {
    // Get iframe references and bounding boxes
    const iframe = document.querySelector("iframe");
    const iframeWindow = iframe.contentWindow;
    const iframeRect = iframe.getBoundingClientRect();
    const toRect = to.getBoundingClientRect();
    const fromRect = from.getBoundingClientRect();

    // Compute absolute start and end positions on the page (accounting for iframe offset)
    const pageStartX = iframeRect.left + to.getBoundingClientRect().left;
    const pageStartY = iframeRect.top + to.getBoundingClientRect().top;
    const startX = fromRect.left + fromRect.width * width;
    const startY = fromRect.top + fromRect.height * height;
    const endX = pageStartX + toRect.width * width;
    const endY = pageStartY + toRect.height * height;

    // ---- Simulate the drag sequence ----
    // 1. Press down on the source element
    triggerPointerEvent(from, "pointerdown", { clientX: startX, clientY: startY });
    await waitNextFrame();

    // 2. Move gradually toward the destination
    for (let step = 1; step <= steps; step++) {
        const progress = step / steps;
        const currentX = startX + (endX - startX) * progress;
        const currentY = startY + (endY - startY) * progress;
        triggerPointerEvent(iframeWindow, "pointermove", { clientX: currentX, clientY: currentY});
        await waitNextFrame();
    }

    // 3. Release (drop) on the target element
    triggerPointerEvent(to, "pointerup", { clientX: endX, clientY: endY });

    // 4. Wait one more frame to allow the UI to update after the drop
    await waitNextFrame();
}

export default {
    dragAndDropSignItemAtHeight,
};
