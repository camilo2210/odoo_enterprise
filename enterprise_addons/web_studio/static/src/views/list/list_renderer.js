import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useService } from "@web/core/utils/hooks";

import "@web_enterprise/views/list/list_renderer_desktop";

export const patchListRendererStudio = () => ({
    setup() {
        super.setup(...arguments);
        this.studioService = useService("studio");
        let opening = false;
        this.openStudio = async () => {
            if (!opening) {
                opening = true;
                try {
                    await this.studioService.open();
                } finally {
                    opening = false;
                }
            }
        };
    },
    /**
     * This function opens the studio mode with current view
     *
     * @override
     */
    onSelectedAddCustomField() {
        this.openStudio();
    },

    isStudioEditable() {
        return !this.studioService.mode && super.isStudioEditable();
    },
});

export const unpatchListRendererStudio = patch(ListRenderer.prototype, patchListRendererStudio());
