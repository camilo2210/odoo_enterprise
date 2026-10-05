import { astToFormula, helpers, registries } from "@odoo/o-spreadsheet";
import { OdooEvaluationPlugin } from "@spreadsheet/plugins";

const { toNumber } = helpers;
const { evaluationPluginRegistry } = registries;

export class SurveyPlugin extends OdooEvaluationPlugin {
    static getters = [
        "getSurveyResults",
        "getSurveyIdFromPosition",
        "getSurveyUserInputIdFromPosition",
    ];

    get serverData() {
        return this.getters.getServerData();
    }

    getSurveyResults(surveyId) {
        const data = this.serverData.batch.get(
            "survey.survey",
            "get_survey_results_for_spreadsheet",
            surveyId
        );
        return data;
    }

    getSurveyIdFromPosition(position) {
        const cell = this.getters.getCorrespondingFormulaCell(position);
        const evaluatedCell = this.getters.getEvaluatedCell(position);
        if (evaluatedCell.type === "error") {
            return undefined;
        }
        const sheetId = position.sheetId;
        if (cell && cell.isFormula && cell.compiledFormula.toFormulaString(this.getters).startsWith("=ODOO.SURVEY(")) {
            const surveyFunction = cell.compiledFormula.getFunctionsFromTokens([
                "ODOO.SURVEY",
            ], this.getters)[0];
            if (surveyFunction) {
                try {
                    const content = astToFormula(surveyFunction.args[0]);
                    const surveyId = this.getters.evaluateFormula(sheetId, content);
                    const locale = this.getters.getLocale();
                    return toNumber(surveyId, locale);
                } catch {
                    return undefined;
                }
            }
        }
        return undefined;
    }

    getSurveyUserInputIdFromPosition(position) {
        const surveyId = this.getSurveyIdFromPosition(position);
        const surveyResults = this.getSurveyResults(surveyId);
        if (!surveyId || !surveyResults) {
            return undefined;
        }
        const surveyUserInputIds = surveyResults.user_input_ids;
        const surveyCell = this.getters.getCorrespondingFormulaCell(position);
        const surveyCellPosition = this.getters.getCellPosition(surveyCell.id);
        const userInputIndex = position.row - surveyCellPosition.row - 1;
        return surveyUserInputIds[userInputIndex];
    }
}

evaluationPluginRegistry.add("SurveyPlugin", SurveyPlugin);
