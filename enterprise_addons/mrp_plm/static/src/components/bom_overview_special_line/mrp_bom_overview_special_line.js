import { patch } from "@web/core/utils/patch";
import { BomOverviewSpecialLine } from "@mrp/components/bom_overview_special_line/mrp_bom_overview_special_line";
import { t, useProps } from "@odoo/owl";

patch(BomOverviewSpecialLine.prototype, {
    setup() {
        super.setup();
        this.plmProps = useProps({
            showOptions: t.object({
                ecos: t.boolean(),
            }),
        });
    },

    get showEcos() {
        return this.props.showOptions.mode == 'overview' && this.plmProps.showOptions.ecos;
    },
});
