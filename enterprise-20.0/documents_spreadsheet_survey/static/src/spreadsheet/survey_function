/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

import { helpers, registries, EvaluationError } from "@odoo/o-spreadsheet";
const { arg, toNumber } = helpers;

registries.functionRegistry.add("ODOO.SURVEY", {
    description: _t("Return the results of a survey."),
    args: [arg("survey_id (number)", _t("The survey id"))],
    category: "Odoo",
    computeArray: function (surveyId) {
        surveyId = toNumber(surveyId, this.locale);
        const surveyResults = this.getters.getSurveyResults(surveyId);
        if (!surveyResults) {
            return new EvaluationError(_t("Survey %(surveyId)s not available", { surveyId }));
        }
        return surveyResults.survey_table;
    },
});
