import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

export class AppointmentsOptionPlugin extends Plugin {
    static id = "AppointmentsOption";
    static dependencies = ["dynamicSnippetCarouselOption", "dynamicSnippetOption"];
    static shared = [
        "getModelNameFilter",
    ];
    modelNameFilter = "appointment.type";
    resources = {
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
        floating_snippet_scope_providers: withSequence(20, {
            label: _t("All Appointments"),
            containerSelector:
                "#oe_structure_appointments_info_3, #oe_structure_appointments_info_2, #oe_structure_appointments_info_1",
        }),
    };
    getModelNameFilter() {
        return this.modelNameFilter;
    }
    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches(".s_appointments, .s_appointments_carousel")) {
            const optionKey = snippetEl.matches(".s_appointments_carousel")
                ? "dynamicSnippetCarouselOption"
                : "dynamicSnippetOption";
            await this.dependencies[optionKey].setOptionsDefaultValues(
                snippetEl,
                this.modelNameFilter
            );
        }
    }
}

registry
    .category("website-plugins")
    .add(AppointmentsOptionPlugin.id, AppointmentsOptionPlugin);
