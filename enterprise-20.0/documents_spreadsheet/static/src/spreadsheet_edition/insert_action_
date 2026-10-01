import { InsertViewSpreadsheet } from "@spreadsheet_edition/assets/insert_action_link_menu/insert_action_link_menu";
import { patch } from "@web/core/utils/patch";

patch(InsertViewSpreadsheet.prototype, {
    async getViewDescription() {
        const { resModel } = this.env.searchModel;
        if (resModel !== "documents.document") {
            return super.getViewDescription(...arguments);
        }
        const { actionId, viewType, domain: configDomain, views } = this.env.config;
        const { xmlId, domain: actionDomain } = actionId
            ? await this.actionService.loadAction(actionId, this.env.searchModel.context)
            : {};
        const { context } = this.env.searchModel.getIrFilterValues();
        const currentUserFolderId = this.env.searchModel.getSelectedFolderId();
        const action = {
            xmlId,
            domain: actionDomain ?? configDomain,
            context: {
                ...context,
                searchpanel_default_user_folder_id: currentUserFolderId.toString(),
                documents_show_default_breadcrumb: true,
            },
            modelName: resModel,
            views,
        };
        return { action, viewType };
    },
});
