import { registry } from "@web/core/registry";
import { belgiumAdditionalPersonalInfo } from "./belgium_additional_personal_info";
import {
    salaryConfigTourStart,
    salaryConfigTourPersonalInfo,
    salaryConfigTourSubmitAndSign,
} from "@hr_contract_salary/../tests/tours/hr_contract_salary_applicant_flow_tour";

registry.category("web_tour.tours").add("hr_contract_salary_applicant_flow_tour_belgium", {
    steps() {
        return [
            ...salaryConfigTourStart(),
            ...salaryConfigTourPersonalInfo(),
            ...belgiumAdditionalPersonalInfo(),
            ...salaryConfigTourSubmitAndSign(),
        ];
    },
});
