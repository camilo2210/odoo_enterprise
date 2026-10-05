import { BaseOptionComponent } from "@html_builder/core/base_option_component";
import { useDynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_hook";
import { registry } from "@web/core/registry";

export class AppointmentsOption extends BaseOptionComponent {
    static id = "appointments_option";
    static template = "website_appointment.AppointmentsOption";
    static dependencies = ["AppointmentsOption"];

    setup() {
        super.setup();
        const { getModelNameFilter } = this.dependencies.AppointmentsOption;
        this.modelNameFilter = getModelNameFilter();
        this.dynamicOptionParams = useDynamicSnippetOption(this.modelNameFilter);
    }
}

registry.category("website-options").add(AppointmentsOption.id, AppointmentsOption);
