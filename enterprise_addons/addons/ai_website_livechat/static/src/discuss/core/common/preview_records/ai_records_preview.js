import { Component, useProps, types } from "@odoo/owl";
import { uniqueId } from "@web/core/utils/functions";
import {
    CARD_SELECTOR,
    INERT_PREVIEW_CONTROL_SELECTOR,
    useAIPreviewCardSet,
} from "./use_ai_preview_cards";

const CARD_CLICK_BEHAVIOR = {
    // These elements handle their own action
    selfHandled: ["a[href]", "button", "[data-bs-toggle]"].join(", "),
    inert: INERT_PREVIEW_CONTROL_SELECTOR,
    // On mobile, keep chat open for in-page interactions
    keepOpen: [
        ".o_wslides_js_slide_like_up",
        ".o_wslides_js_slide_like_down",
        ".o_wsale_attribute_previewer",
        ".o_add_wishlist",
    ].join(", "),
};

export class AIPreviewCardSet extends Component {
    static template = "ai_website_livechat.AIPreviewCardSet";

    setup() {
        this.props = useProps({
            previewSet: types.object(),
            thread: types.object().optional(),
        });
        this.slotName = uniqueId("AICardslot");
        this.previewCards = useAIPreviewCardSet(
            this.props.previewSet,
            this.slotName,
            this.env.services["public.interactions"]
        );
        this.cardsHostRef = this.previewCards.cardsHostRef;
        this.carousel = this.previewCards.carousel;
    }

    onCardClick(ev) {
        const originalTarget = ev.composedPath().find((target) => target instanceof Element);
        if (!originalTarget) {
            return;
        }
        const card = originalTarget.closest(CARD_SELECTOR);
        if (!card) {
            return;
        }
        if (originalTarget.closest(CARD_CLICK_BEHAVIOR.inert)) {
            return;
        }

        // On mobile, fold the chat unless the click targets an in-page interaction.
        if (this.env.services.ui.isSmall && !originalTarget.closest(CARD_CLICK_BEHAVIOR.keepOpen)) {
            this._foldChatWindow();
        }
        // Navigate to the card URL unless the click targets a self-handled element (link, button…).
        if (!originalTarget.closest(CARD_CLICK_BEHAVIOR.selfHandled) && card.dataset.href) {
            window.open(card.dataset.href, "_blank", "noopener");
        }
    }

    _foldChatWindow() {
        this.props.thread?.channel?.chatWindow?.fold();
    }
}

export class AIRecordsPreview extends Component {
    static template = "ai_website_livechat.AIRecordsPreview";
    static components = { AIPreviewCardSet };

    setup() {
        this.props = useProps({
            message: types.object(),
            thread: types.object().optional(),
        });
    }

    get previewSets() {
        return (this.props.message.ai_record_previews?.preview_sets ?? []).filter(
            ({ records }) => records?.length
        );
    }
}
