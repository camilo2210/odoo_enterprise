import { WebClient } from "@web/webclient/webclient";
import { getService, mountWithCleanup } from "@web/../tests/web_test_helpers";
import { prepareWebClientForSpreadsheet } from "@spreadsheet_edition/../tests/helpers/webclient_helpers";
import { makeDocumentsSpreadsheetMockEnv } from "./model";
import { getBasicServerData } from "./data";

/**
 * Get a webclient with a kanban view.
 * The webclient is already configured to work with spreadsheet (env, registries, ...)
 *
 * @param {Object} params
 * @param {string} [params.model] Model name of the kanban
 * @param {Object} [params.serverData] Data to be injected in the mock server
 * @param {Function} [params.mockRPC] Mock rpc function
 * @param {object} [params.additionalContext] additional action context
 * @param {Object} [params.groupBy]
 * @returns {Promise<object>} Webclient
 */
export async function spawnKanbanViewForSpreadsheet(params = {}) {
    const { model, serverData, mockRPC } = params;
    await prepareWebClientForSpreadsheet();
    await makeDocumentsSpreadsheetMockEnv({
        serverData: serverData || getBasicServerData(),
        mockRPC,
    });

    const webClient = await mountWithCleanup(WebClient);
    await getService("action").doAction(
        {
            name: "Partners",
            res_model: model || "partner",
            type: "ir.actions.act_window",
            views: [[false, "kanban"]],
            context: {
                group_by: params.groupBy || [],
            },
        },
        {
            viewType: "kanban",
            additionalContext: params.additionalContext || {},
        }
    );
    return webClient;
}
