import { GraphRenderer } from "@web/views/graph/graph_renderer";
import { user } from "@web/core/user";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { SpreadsheetSelectorDialog } from "@spreadsheet_edition/assets/components/spreadsheet_selector_dialog/spreadsheet_selector_dialog";
import { omit } from "@web/core/utils/objects";

patch(GraphRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
        this.actionService = useService("action");
        this.menu = useService("menu");
        this.uiService = useService("ui");
        this.canInsertChart = session.can_insert_in_spreadsheet;
    },

    async onInsertInSpreadsheet() {
        const { actionId } = this.env.config;
        const { xml_id } = actionId
            ? await this.actionService.loadAction(actionId, this.env.searchModel.context)
            : {};
        const context = omit(
            this.model.searchParams.context,
            ...Object.keys(user.context),
            "graph_measure",
            "graph_order"
        );
        const actionOptions = {
            preProcessingAsyncAction: "insertChart",
            preProcessingAsyncActionData: {
                metaData: {
                    ...this.model.metaData,
                    axisType: this.chart.instance().scales.x?.type,
                },
                searchParams: {
                    ...this.model.searchParams,
                    domain: this.env.searchModel.domainString,
                    context,
                },
                actionXmlId: xml_id,
            },
        };
        const params = {
            type: "GRAPH",
            name: this.model.metaData.title,
            actionOptions,
            context,
        };
        this.env.services.dialog.add(SpreadsheetSelectorDialog, params);
    },
});
