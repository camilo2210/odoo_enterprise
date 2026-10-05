import { patch } from "@web/core/utils/patch";
import { BomOverviewTable } from "@mrp/components/bom_overview_table/mrp_bom_overview_table";
import { t, useProps } from "@odoo/owl";

patch(BomOverviewTable.prototype, {
    setup() {
        super.setup();
        this.plmProps = useProps({
            showOptions: t.object({
                ecos: t.boolean(),
            }),
        });
    },

    //---- Getters ----

    get showEcos() {
        return this.props.showOptions.mode == 'overview' && this.plmProps.showOptions.ecos;
    },
});
