import { startServer } from "@mail/../tests/mail_test_helpers";
import { Store } from "@mail/../tests/mock_server/store";

import {
    getTestApp,
    makeTestApp,
    serverState,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { getDocumentsModel } from "./data";
import { session } from "@web/session";

/**
 * Create a mocked server environment
 *
 * @param {{ serverData?: Record<string, any[]> }} [params]
 */
export async function makeDocumentsMockEnv(params) {
    if (params?.serverData) {
        for (const [modelName, records] of Object.entries(params.serverData)) {
            if (!records?.length) {
                continue;
            }
            const PyModel = getDocumentsModel(modelName);
            if (!PyModel) {
                throw new Error(`Model ${modelName} not found inside DocumentsModels`);
            }
            PyModel._records = structuredClone(records);
        }
    }
    const pyEnv = await startServer();
    pyEnv["res.users"].write(serverState.userId, { notification_type: "inbox" });
    const ResUsers = pyEnv["res.users"];
    const store = new Store();
    ResUsers._init_store_data(store);
    patchWithCleanup(session, { storeData: store.as_dict() });
    if (!getTestApp()) {
        await makeTestApp();
    }
}
