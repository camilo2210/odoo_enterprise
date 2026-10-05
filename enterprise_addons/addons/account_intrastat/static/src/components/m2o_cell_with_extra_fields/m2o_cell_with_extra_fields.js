import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { computeM2OProps } from "@web/views/fields/many2one/many2one";
import { ProductLabelSectionAndNoteListRender } from '@account/components/product_label_section_and_note_o2m/product_label_section_and_note_field_o2m';
import { M2OCellWithExtraFields } from '@account/components/m2o_cell_with_extra_fields/m2o_cell_with_extra_fields';

patch(ProductLabelSectionAndNoteListRender.prototype, {
    getActiveColumns() {
        let activeColumns = super.getActiveColumns();
        // Always remove the intrastat_product_origin_country_id column from active columns & show under intrastat
        return activeColumns.filter((col) => col.name !== "intrastat_product_origin_country_id");
    },
    get optionalFieldGroups() {
        let optionalFieldGroups = super.optionalFieldGroups;
        for (let group of optionalFieldGroups) {
            group.optionalFields = group.optionalFields.filter((field) => field.name !== "intrastat_product_origin_country_id");
        }
        return optionalFieldGroups;
    }
});


patch(M2OCellWithExtraFields.prototype, {
    get extraProductCountryProps() {
        const m2oProps = computeM2OProps({
            ...this.props,
            name: "intrastat_product_origin_country_id",
            placeholder: _t("Select a Product Country"),
            string: _t("Product Country"),
            canOpen: false,
            canCreate: false,
            context: undefined,
            domain: undefined,
        });
        return {
            props: {
                ...m2oProps,
                readonly: this.isReadonlyList,
            },
            invisible: this.props.name !== 'intrastat_transaction_id' || !this.props.record.data.intrastat_transaction_id,
        }
    }
});
