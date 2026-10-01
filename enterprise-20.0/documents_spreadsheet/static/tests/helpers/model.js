import { makeSpreadsheetMockEnv } from "@spreadsheet/../tests/helpers/model";
import { getService, serverState } from "@web/../tests/web_test_helpers";
import { getDocumentBasicData } from "./data";

export const makeDocumentsSpreadsheetMockEnv = async (params = {}) => {
    params.serverData = ensureDocumentsRequiredRecords(params.serverData);
    await makeSpreadsheetMockEnv(params);
    getService("document.document").store.odoobot = { userId: serverState.odoobotId };
};

export const ensureDocumentsRequiredRecords = (serverData) => {
    const res = { ...(serverData || {}) };
    if (!serverData?.models?.["res.users"]) {
        const resUsers = getDocumentBasicData().models["res.users"];
        if (!serverData || !serverData.models) {
            res.models = { "res.users": resUsers };
        } else if (!serverData.models["res.users"]) {
            res.models["res.users"] = resUsers;
        }
    }
    return res;
};
