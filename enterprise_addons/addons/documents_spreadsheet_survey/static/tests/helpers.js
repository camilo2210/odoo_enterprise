import { defineDocumentSpreadsheetModels } from "@documents_spreadsheet/../tests/helpers/data";
import { animationFrame } from "@odoo/hoot-mock";
import { setCellContent } from "@spreadsheet/../tests/helpers/commands";
import { SpreadsheetModels } from "@spreadsheet/../tests/helpers/data";
import { createModelWithDataSource } from "@spreadsheet/../tests/helpers/model";
import { fields, models } from "@web/../tests/web_test_helpers";
import { patchSpreadsheetExternalShareFunctionCheck } from "@documents_spreadsheet/bundle/actions/external_share_function";

export const MOCK_SURVEY_DATA = {
    survey_table: [
        [{value: "Timestamp"}, {value: "2024-05-01 12:00:00"}, {value: "2024-05-02 12:00:00"}],
        [{value: "How are you ?"}, {value: "Just fine !"}, {value: "Good"}],
        [{value: "What's your age ?"}, {value: 25}, {value: 35}],
    ],
    user_input_ids: [5, 6],
    survey_name: "Test Survey",
};

export class SurveySurvey extends models.Model {
    _name = "survey.survey";

    title = fields.Char({ string: "Title" });
    _records = [{ id: 1, title: "Test Survey" }];

    get_survey_results_for_spreadsheet() {
        return [MOCK_SURVEY_DATA];
    }
}

export function defineDocumentSpreadsheetSurveyModels() {
    const DocumentSpreadsheetSurveyModels = { SurveySurvey };
    Object.assign(SpreadsheetModels, DocumentSpreadsheetSurveyModels);
    defineDocumentSpreadsheetModels();
    patchSpreadsheetExternalShareFunctionCheck(); // Patch function registry
}

export async function createModelWithSurvey() {
    const { model } = await createModelWithDataSource({
        mockRPC: async function (route, args) {
            if (args.method === "get_survey_results_for_spreadsheet") {
                return [MOCK_SURVEY_DATA];
            }
        },
    });
    setCellContent(model, "A1", `=ODOO.SURVEY("1")`);
    await animationFrame();
    return model;
}
