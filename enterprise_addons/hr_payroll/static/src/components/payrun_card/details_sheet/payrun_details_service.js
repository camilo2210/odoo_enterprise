import { proxy } from "@odoo/owl";
import { registry } from "@web/core/registry";

export const payRunDetailsService = {
    start() {
        const state = proxy({
            templates: null,
            renderingContext: null,
            isPayRunReady: null,
            onClickViewButton: null,
        });
        let closeSheet = null;
        return {
            state,
            publish({ templates, renderingContext, isPayRunReady, onClickViewButton }) {
                state.templates = templates;
                state.renderingContext = renderingContext;
                state.isPayRunReady = isPayRunReady;
                state.onClickViewButton = onClickViewButton;
            },
            get isOpen() {
                return Boolean(closeSheet);
            },
            setOpen(close) {
                closeSheet = close;
            },
            clear() {
                closeSheet = null;
            },
            close() {
                const close = closeSheet;
                closeSheet = null;
                close?.();
            },
        };
    },
};

registry.category("services").add("payRunDetails", payRunDetailsService);
