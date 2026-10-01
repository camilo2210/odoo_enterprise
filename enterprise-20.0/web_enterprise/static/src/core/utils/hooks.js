import { proxy, untrack } from "@odoo/owl";
import { couldBeScrollableY } from "@web/core/utils/scrolling";
import { useLayoutEffect } from "@web/owl2/utils";

/**
 * This file contains various custom enterprise hooks.
 * Their inner working is rather simple:
 * Each custom hook simply hooks itself to any number of owl lifecycle hooks.
 * You can then use them just like an owl hook in any Component
 * e.g.:
 * import { useBus } from "@web/core/utils/hooks";
 * ...
 * setup() {
 *    ...
 *    useBus(someBus, someEvent, callback)
 *    ...
 * }
 */

// -----------------------------------------------------------------------------
// useSticky
// -----------------------------------------------------------------------------

/**
 * Detects when a `position: sticky; top: 0` element is actually stuck.
 * Listens to scroll events on the element's parent (or an explicit container)
 * and sets `isSticky` whenever `scrollTop > 0`.
 *
 * @param {import("@odoo/owl").Signal<HTMLElement|null>|Ref} ref
 * @param {Object} [options]
 * @param {Element} [options.root] scroll container. Defaults to `el.parentElement`.
 * @returns {{ readonly isSticky: boolean }}
 */
export function useSticky(ref, { root } = {}) {
    const state = proxy({ isSticky: false });
    const getEl = () => (ref ? untrack(ref) : undefined);

    useLayoutEffect(
        (el) => {
            if (!el) {
                return;
            }
            let node = el.parentElement;
            while (node && !couldBeScrollableY(node)) {
                node = node.parentElement;
            }
            const containerEl = root ?? node ?? document.documentElement;
            const onScroll = () => {
                state.isSticky = containerEl.scrollTop > 0;
            };
            containerEl.addEventListener("scroll", onScroll);
            return () => {
                containerEl.removeEventListener("scroll", onScroll);
                state.isSticky = false;
            };
        },
        () => [getEl()]
    );
    return state;
}
