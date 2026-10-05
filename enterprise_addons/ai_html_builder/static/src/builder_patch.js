import { patch } from "@web/core/utils/patch";
import { Builder } from "@html_builder/builder";
import { triggers, useDataGetter } from "@ai/utils/bus_data_getter";

triggers.add("htmlBuilder");

patch(Builder.prototype, {
    setup() {
        super.setup();
        useDataGetter("htmlBuilder", () => ({
            callWithBuilderMutex: (fn, params) => this.editor.shared.operation.next(fn, params),
            blockBuilderUI: (loadingEffectDelay) => {
                const removeLoadingElement = this.editor.shared.operation.addLoadingElement(
                    true, loadingEffectDelay
                );
                const sidebarEl = this.builderSidebarRef();
                sidebarEl?.classList.add("o_builder_disabled");
                return () => {
                    sidebarEl?.classList.remove("o_builder_disabled");
                    removeLoadingElement();
                };
            },
        }));
    },
});
