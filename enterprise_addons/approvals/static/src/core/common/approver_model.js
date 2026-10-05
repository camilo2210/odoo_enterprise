import { Record } from "@mail/model/export";

export class ApprovalApprover extends Record {
    static _name = "approval.approver";
    /** @type {number} */
    id;
    /** @type {"new"|"pending"|"approved"|"refused"|"cancel"} */
    status;
    /** @type {number} id of the approver's user, to tell whether self is the approver */
    user_id;
}

ApprovalApprover.register();
