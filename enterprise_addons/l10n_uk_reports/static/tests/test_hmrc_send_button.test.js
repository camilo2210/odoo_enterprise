import { describe, expect, test } from "@odoo/hoot";
import { SendHmrcButton } from "@l10n_uk_reports/components/send_hmrc/send_hmrc";
import { mountWithCleanup, defineModels, onRpc } from "@web/../tests/web_test_helpers";
import { click } from "@odoo/hoot-dom";
import { mailModels } from "@mail/../tests/mail_test_helpers";

// Due to dependency with mail module, we have to define their models for our tests.
defineModels(mailModels);

describe("SendHmrcButton - retrieveClientInfo", () => {

    test("retrieveClientInfo function works correctly", async () => {
        const mockProps = {
            record: {
                data: {
                    obligation_id: {id: 1, clientData: "Test Obligation"},
                    hmrc_gov_client_device_id: "test-device-123"
                },
                context: {},
            }
        };

        onRpc('action_submit_vat_return', () => true);

        await mountWithCleanup(SendHmrcButton, { props: mockProps });
        
        localStorage.removeItem('hmrc_gov_client_device_id');
        
        expect('a[role="button"]').toHaveCount(1);
        await click('a[role="button"]');

        localStorage.removeItem('hmrc_gov_client_device_id');
    });
});
