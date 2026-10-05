import { mailModels } from "@mail/../tests/mail_test_helpers";

export class MailActivity extends mailModels.MailActivity {
    _store_activity_fields(res) {
        super._store_activity_fields(res);
        /** @type {import("mock_models").ApprovalApprover} */
        const ApprovalApprover = this.env["approval.approver"];
        // mock: _compute_approver_id is not simulated, look up the approver directly
        res.one("approver_id", ["status", "user_id"], {
            value: (activity) =>
                activity.res_model === "approval.request"
                    ? ApprovalApprover.browse(
                          ApprovalApprover._filter([
                              ["request_id", "=", activity.res_id],
                              ["user_id", "=", activity.user_id],
                          ])
                              .map((approver) => approver.id)
                              .slice(0, 1)
                      )
                    : ApprovalApprover.browse([]),
        });
    }
}
