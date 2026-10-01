import { HrApplicant } from "@hr_recruitment/../tests/mock_server/mock_models/hr_applicant";
import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { ResPartner } from "./mock_server/mock_models/res_partner";

export function setupVoipHrRecruitmentTests() {
    setupVoipTests({ extraModels: { HrApplicant, ResPartner } });
}
