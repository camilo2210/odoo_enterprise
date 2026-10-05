import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";

/**
 * Index of the button the view switcher indicator must start from, passed from
 * one control panel to the next: switching view re-renders the whole control
 * panel, so the switcher that runs the transition is instantiated after the
 * button it starts from has been removed.
 *
 * @type {{ actionId?: number, viewType: string, index: number } | null}
 */
let pendingSlide = null;

patch(ControlPanel.prototype, {
    setup() {
        super.setup();
        const { actionId, viewType } = this.env.config;
        const slide = pendingSlide;
        this.slideFromIndex =
            slide && slide.actionId === actionId && slide.viewType === viewType
                ? slide.index
                : this.activeViewIndex;
        onMounted(() => {
            // Reset on mount: one control panel is instantiated per render
            // of the action, and only the last one is mounted.
            if (pendingSlide === slide) {
                pendingSlide = null;
            }
        });
    },

    get activeViewIndex() {
        return this.env.config.viewSwitcherEntries?.findIndex((view) => view.active) ?? -1;
    },

    switchView(viewType, newWindow) {
        // A new window leaves this control panel mounted: no transition to run.
        if (!newWindow) {
            pendingSlide = {
                actionId: this.env.config.actionId,
                viewType,
                index: this.activeViewIndex,
            };
        }
        super.switchView(viewType, newWindow);
    },
});
