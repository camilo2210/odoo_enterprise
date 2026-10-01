import { AttachmentList } from "@mail/core/common/attachment_list";

import { useProps, types } from "@odoo/owl";

import { patch } from "@web/core/utils/patch";

patch(AttachmentList.prototype, {
    setup() {
        super.setup(...arguments);
        this.hrRecruitmentExtractProps = useProps({
            reloadChatterParentView: types.function([]).optional(),
        });
    },
    onConfirmUnlink(attachment) {
        super.onConfirmUnlink(attachment);
        if (attachment.thread?.model === "hr.applicant") {
            this.hrRecruitmentExtractProps.reloadChatterParentView?.();
        }
    },
});
