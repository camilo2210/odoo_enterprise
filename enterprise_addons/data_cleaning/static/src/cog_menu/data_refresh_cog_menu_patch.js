import { patch } from "@web/core/utils/patch";
import { DataRefreshCogMenu, DataRefreshCogMenuItem } from "@data_recycle/cog_menu/data_refresh_cog_menu";

patch(DataRefreshCogMenu.prototype, {

    async refreshData() {
        const model = this.action.currentController?.props?.resModel;

        if (model === "data_cleaning.record") {
            const ruleId = this._getDomainValue("cleaning_model_id");
            return await this.action.doActionButton({
                type: "object",
                resModel: "data_cleaning.model",
                name: "refresh_clean_records",
                context: {
                    cleaning_model_id: ruleId,
                }
            });
        }

        else if (model === "data_merge.record") {
            const ruleId = this._getDomainValue("model_id");
            return await this.action.doActionButton({
                type: "object",
                resModel: "data_merge.model",
                name: "refresh_duplicates_records",
                context: {
                    model_id: ruleId,
                }
            });
        }

        await super.refreshData();
    }
});

DataRefreshCogMenuItem.isDisplayed = ({ searchModel }) => {
    return ["data_recycle.record", "data_cleaning.record", "data_merge.record"].includes(searchModel.resModel);
}
