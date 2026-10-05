import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { computeM2OProps } from "@web/views/fields/many2one/many2one";
import { ProductLabelSectionAndNoteListRender } from '@account/components/product_label_section_and_note_o2m/product_label_section_and_note_field_o2m';
import { M2OCellWithExtraFields } from '@account/components/m2o_cell_with_extra_fields/m2o_cell_with_extra_fields';

patch(ProductLabelSectionAndNoteListRender.prototype, {
    getActiveColumns() {
        let activeColumns = super.getActiveColumns();

        const isDepreciationColumnActive = activeColumns.some((col) => col.name === "depreciation_model_id");
        this.props.list.records.forEach((record) => {
            // Assign based on the global column presence AND the specific record's data
            record.showDepreciation = isDepreciationColumnActive && record.data.display_depreciation_model;
        });

        // Always remove the depreciation model id column from active columns & show under account
        return activeColumns.filter((col) => col.name !== "depreciation_model_id");
    },
    get optionalFieldGroups() {
        let optionalFieldGroups = super.optionalFieldGroups;
        for (let group of optionalFieldGroups) {
            group.optionalFields = group.optionalFields.filter((field) => field.name !== "depreciation_model_id");
        }
        return optionalFieldGroups;
    }
});

patch(M2OCellWithExtraFields.prototype, {
    get extraDepreciationModelProps() {
        const m2oProps = computeM2OProps({
            ...this.props,
            name: "depreciation_model_id",
            placeholder: _t("Select a Depreciation Model"),
            string: _t("Depreciation Model"),
            canOpen: true,
            canQuickCreate: false,
            context: undefined,
            domain: undefined,
        });
        return {
            props: {
                ...m2oProps,
                readonly: this.isReadonlyList,
            },
            invisible: this.props.name !== 'account_id' || !this.props.record.showDepreciation,
        }
    }
});
