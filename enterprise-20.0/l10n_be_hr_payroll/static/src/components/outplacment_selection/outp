import { registry } from "@web/core/registry";
import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";

export class OutplacementSelectionField extends SelectionField {
    /**
     * @override
     * Filters available options based on company sector classification.
     * Removes the "special" option for public sector companies.
     */
    get options() {
        const options = super.options;
        const companySector = this.props.record.data["l10n_be_company_sector"];

        if (companySector === "private") {
            return options;
        }

        return options.filter(([value]) => value !== "special");
    }
}

export const outplacementSelectionField = {
    ...selectionField,
    component: OutplacementSelectionField,
    fieldDependencies: () => [
        {
            name: "l10n_be_company_sector",
            type: "selection",
        },
    ],
};

registry.category("fields").add("outplacement_selection", outplacementSelectionField);
