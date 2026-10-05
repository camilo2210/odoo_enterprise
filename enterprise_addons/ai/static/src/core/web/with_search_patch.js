import { t } from "@odoo/owl";
import { WithSearch, withSearchProps } from "@web/search/with_search/with_search";
import { patch } from "@web/core/utils/patch";
import { useDataGetter } from "@ai/utils/bus_data_getter";

withSearchProps.ai = t.object().optional();

patch(WithSearch.prototype, {
    setup() {
        super.setup(...arguments);
        useDataGetter("view", () => this.getCurrentViewInfo());
    },
    async getCurrentViewInfo() {
        const config = this.env.config;
        const searchModel = this.env.searchModel;
        const result = {};
        // if in form view, no need to return anything
        if (config.viewType === "form") {
            return;
        }
        result.action_name = config.actionName;
        result.action_id = config.actionId;
        result.view_id = config.viewId;
        result.model = searchModel.resModel;
        result.domain = searchModel.domainString;
        result.available_view_types = config.viewSwitcherEntries?.map((v) => v.type) || [];
        result.view_type = config.viewType;
        result.order_by = searchModel.orderBy;
        result.facets = searchModel.facets.map(({ icon, color, ...rest }) => rest);
        return result;
    },
});
