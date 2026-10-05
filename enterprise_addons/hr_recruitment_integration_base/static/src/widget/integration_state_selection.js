import { Component, t, useProps } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

import { registry } from '@web/core/registry';
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class IntegrationStateSelectionField extends Component {
    static template = "hr_recruitment_integration_base.IntegrationStateSelection";

    props = useProps({
        ...standardFieldProps,
        ribbon: t.boolean().optional(),
    });

    setup() {
        super.setup();
        this.colors = {
            'pending': ["info", "info"],
            'warning': ["warning", "warning"],
            'expired': ["muted", "muted"],
            'deleted': ["muted", "300"],
            'failure': ["danger", "danger"],
            'success': ["success", "success"]
        };
        this.titles = {
            'pending': "pending",
            'warning': "warning",
            'expired': "expired",
            'deleted': "deleted",
            'failure': "issue",
            'success': "published",
        }
    }

    get imgClassNames() {
        return `oi oi-fw ${this.value == 'deleted' ? "" : "oi-filled"} o_button_icon text-${this.color[0]}`
    }

    get ribbonClassNames() {
        return `text-bg-${this.color[1]}`
    }

    get color() {
        return this.colors[this.value];
    }

    get title() {
        return this.titles[this.value];
    }

    get value() {
        return this.props.record.data[this.props.name];
    }
}

export const integrationStateSelectionField = {
    component: IntegrationStateSelectionField,
    supportedOptions: [
        {
            label: _t("Ribbon"),
            name: "ribbon",
            type: "boolean",
        },
    ],
    extractProps({ options }) {
        return {'ribbon': Boolean(options.ribbon)};
    },
};

registry.category("fields").add("integration_state_selection", integrationStateSelectionField);
