import { setupVoipTests } from "@voip/../tests/voip_test_helpers";
import { CRMLead } from "@voip_crm/../tests/mock_server/mock_models/crm_lead";
import { ResPartner } from "@voip_crm/../tests/mock_server/mock_models/res_partner";

export function setupVoipCRMTests() {
    setupVoipTests({ extraModels: { CRMLead, ResPartner } });
}
