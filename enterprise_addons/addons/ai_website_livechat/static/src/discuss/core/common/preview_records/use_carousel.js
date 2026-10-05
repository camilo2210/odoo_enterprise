import { proxy } from "@odoo/owl";

// Sub-pixel rounding and fractional scroll positions can make scrollLeft
// differ from the theoretical maximum by a small amount; 2 px absorbs that.
const SCROLL_TOLERANCE_PX = 2;

/**
 * Reactive carousel state and navigation for a horizontally-scrollable
 * card container.
 *
 * @param {Function} rootRef - Signal containing the root whose descendants
 *     include the scrollable `.o_ai_preview_cards` wrapper.
 * @param {string} cardSelector - CSS selector matching individual card
 *     elements inside the wrapper.
 */
export function useCarousel(rootRef, cardSelector) {
    const state = proxy({
        current: 0,
        canScroll: false,
        visibleCount: 1,
        hasPrev: false,
        hasNext: false,
    });

    function getInner() {
        return rootRef()?.querySelector(".o_ai_preview_cards") ?? null;
    }

    function getCards(inner = getInner()) {
        return inner ? inner.querySelectorAll(cardSelector) : [];
    }

    /**
     * Sync reactive state with the current scroll position.
     * Called on scroll events and when the container resizes.
     */
    function update() {
        const inner = getInner();
        if (!inner) {
            return;
        }
        const cards = getCards(inner);
        const scrollMax = inner.scrollWidth - inner.clientWidth;
        state.canScroll = scrollMax > SCROLL_TOLERANCE_PX;
        state.hasPrev = inner.scrollLeft > SCROLL_TOLERANCE_PX;
        state.hasNext = inner.scrollLeft < scrollMax - SCROLL_TOLERANCE_PX;

        const card = cards[0];
        const gap = parseFloat(getComputedStyle(inner).columnGap) || 0;
        const step = (card?.offsetWidth ?? 0) + gap;
        state.current = step ? Math.round(inner.scrollLeft / step) : 0;
        state.visibleCount = card?.offsetWidth
            ? Math.max(1, Math.floor(inner.clientWidth / card.offsetWidth))
            : 1;
    }

    /**
     * Smooth-scroll so that the card at `index` is visible.
     * The last card aligns to the end so no trailing gap is shown.
     */
    function goTo(index) {
        const inner = getInner();
        if (!inner) {
            return;
        }
        const cards = getCards(inner);
        state.current = Math.max(0, Math.min(index, cards.length - 1));
        const target = cards[state.current];
        if (!target) {
            return;
        }
        const inline = state.current === cards.length - 1 ? "end" : "start";
        target.scrollIntoView({ behavior: "smooth", block: "nearest", inline });
    }

    return {
        state,
        update,
        get hasPrev() {
            return state.hasPrev;
        },
        get hasNext() {
            return state.hasNext;
        },
        goTo,
        prev: () => goTo(state.current - state.visibleCount),
        next: () => goTo(state.current + state.visibleCount),
    };
}
