import { markup, onWillStart, signal, useEffect } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { Cache } from "@web/core/utils/cache";
import { setElementContent } from "@web/core/utils/html";
import { useCarousel } from "./use_carousel";

export const CARD_SELECTOR = ".o_ai_preview_card";
const INERT_PREVIEW_CONTROL_CLASS = "o_ai_preview_inert_control";
export const INERT_PREVIEW_CONTROL_SELECTOR = `.${INERT_PREVIEW_CONTROL_CLASS}`;
const WEBSITE_FILTER_CONTROL_SELECTOR = ".o_ai_preview_card .post_link";

/**
 * Hook that loads and displays a set of AI preview cards.
 *
 * - Fetches card HTML from the cache before the component mounts.
 * - After mount, injects the HTML into the DOM, sets up responsive layout,
 *   and starts any website interactions.
 */
export function useAIPreviewCardSet(previewSet, slotName, interactions) {
    const cardsHostRef = signal.ref();
    const cardsContainerRef = signal.ref();
    const carousel = useCarousel(cardsContainerRef, CARD_SELECTOR);
    const previewCards = {
        html: "",
        cardsHostRef,
        carousel,
    };

    // Fetch card HTML before the component renders so it's ready to inject.
    onWillStart(async () => {
        const { model, records } = previewSet;
        const recordIds = records.map((record) => record.id);
        if (!model || !recordIds.length) {
            return;
        }
        const result = await previewCardsCache.read(model, recordIds);
        if (result?.count > 0) {
            previewCards.html = result.html;
        }
    });

    // Once the host element is in the DOM and we have HTML, inject the cards
    // and wire up layout + interactions.
    useEffect(() => {
        const cardsHost = cardsHostRef();
        if (!cardsHost || !previewCards.html) {
            return;
        }

        const container = insertPreviewCardsHtml(cardsHost, previewCards.html, slotName);
        cardsContainerRef.set(container);

        const cleanupLayout = setupPreviewCardsLayout(cardsHost, container, carousel.update);
        const cleanupInteractions = setupPreviewCardsInteractions(container, interactions);

        return () => {
            cleanupLayout();
            cleanupInteractions();
            container.remove();
            cardsContainerRef.set(null);
        };
    });

    return previewCards;
}

export const previewCardsCache = new Cache((model, recordIds) =>
    rpc("/ai/preview_cards", { model, record_ids: recordIds }).then(
        (result) => {
            if (!result?.html || typeof result.html !== "string") {
                return null;
            }
            return { html: markup(result.html), count: result.count };
        },
        () => null
    )
);

// Creates the card container from server HTML and inserts it into the DOM.
function insertPreviewCardsHtml(cardsHost, html, slotName) {
    const container = createPreviewCardsContainer(html);
    mountPreviewCardsContainer(cardsHost, container, slotName);
    return container;
}

//Turns raw server HTML into a safe, ready-to-mount container.
function createPreviewCardsContainer(html) {
    const container = document.createElement("div");
    container.style.display = "contents";
    setElementContent(container, html || "");
    openLinksInNewTab(container);
    makeWebsiteFilterControlsInert(container);
    return container;
}

/**
 * Mounts the card container in the right place depending on context.
 * - Livechat widget uses a shadow DOM, so the container goes through a named
 *   slot on the shadow host.
 * - Backend chat is a regular DOM, so we just append directly to the host.
 */
function mountPreviewCardsContainer(cardsHost, container, slotName) {
    const rootNode = cardsHost.getRootNode();
    if (rootNode instanceof ShadowRoot) {
        container.slot = slotName;
        rootNode.host.appendChild(container);
    } else {
        cardsHost.appendChild(container);
    }
}

// Starts public website interactions inside the injected cards.
function setupPreviewCardsInteractions(cardsContainer, interactions) {
    interactions?.startInteractions(cardsContainer);
    return () => interactions?.stopInteractions(cardsContainer);
}

/**
 * Keeps the carousel in sync with the card container's size and scroll position.
 * - A ResizeObserver watches the host and switches between wide/narrow card
 *   sizing at 420 px.
 * - A scroll listener on the inner card row updates the carousel nav state.
 */
function setupPreviewCardsLayout(cardsHost, cardsContainer, updateCarousel) {
    const inner = cardsContainer.querySelector(".o_ai_preview_cards");
    const updateLayout = () => {
        if (inner) {
            const isNarrow = cardsHost.offsetWidth < 420;
            inner.style.setProperty(
                "--o-ai-card-basis",
                isNarrow ? "var(--o-ai-card-basis-narrow)" : "var(--o-ai-card-basis-wide)"
            );
        }
        updateCarousel();
    };

    const ro = new ResizeObserver(updateLayout);
    ro.observe(cardsHost);
    updateLayout();
    inner?.addEventListener("scroll", updateCarousel, { passive: true });

    return () => {
        ro.disconnect();
        inner?.removeEventListener("scroll", updateCarousel);
    };
}

// Forces every link inside the cards to open in a new tab.
function openLinksInNewTab(root) {
    for (const el of root.querySelectorAll("a[href]")) {
        el.target = "_blank";
        el.rel = "noopener noreferrer";
    }
}

// Strips the click/navigation behavior from website filter badges (.post_link).
function makeWebsiteFilterControlsInert(root) {
    for (const el of root.querySelectorAll(WEBSITE_FILTER_CONTROL_SELECTOR)) {
        el.removeAttribute("href");
        el.removeAttribute("data-post");
        el.classList.remove("post_link", "cursor-pointer", "o_badge_clickable");
        el.classList.add(INERT_PREVIEW_CONTROL_CLASS);
    }
}
