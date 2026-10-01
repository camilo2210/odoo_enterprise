declare module "models" {
    import { ApprovalApprover as ApprovalApproverClass } from "@approvals/core/common/approver_model";

    export interface ApprovalApprover extends ApprovalApproverClass {}

    export interface Activity {
        approver_id: ApprovalApprover;
    }
    export interface Store {
        "approval.approver": StaticMailRecord<ApprovalApprover, typeof ApprovalApproverClass>;
    }

    export interface Models {
        "approval.approver": ApprovalApprover;
    }
}
