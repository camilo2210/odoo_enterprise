import { serverState } from "@web/../tests/web_test_helpers";

/**
 * @param {Number|undefined} id omitted for a record the mock server creates itself
 * @param {String} name
 * @param {object?} data
 * @return {{}}
 */
export function makeDocumentRecordData(id, name, data = {}) {
    const strippedName = name.replace(/\s/g, "");
    const defaultValues = {
        available_embedded_actions_ids: [],
        folder_id: false,
        company_id: false,
        owner_id: false,
        partner_id: false,
        type: "binary",
    };
    const documentType = data.type || defaultValues.type;
    const user_folder_id =
        data.user_folder_id ||
        (data.folder_id
            ? data.folder_id.toString()
            : data.owner_id
            ? data.owner_id === serverState.userId
                ? "MY"
                : "SHARED"
            : "COMPANY");
    const record = {
        ...defaultValues,
        access_token: `accessToken${strippedName}`,
        is_folder: documentType === "folder",
        name,
        type: documentType,
        user_folder_id,
        ...data,
    };
    if (id !== undefined) {
        // create() assigns its own id, and refuses a given one
        record.id = id;
    }
    return record;
}
