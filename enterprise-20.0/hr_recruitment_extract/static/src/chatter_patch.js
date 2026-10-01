import { Chatter } from "@mail/chatter/web_portal_project/chatter";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(Chatter.prototype, {
    setup() {
        super.setup();
        this.attachmentUploadService = useService("mail.attachment_upload");
        this.attachmentUploadService.onFileUploaded(this.thread, (thread) => {
            if (thread.model === "hr.applicant") {
                this.reloadParentView();
            }
        });
    },
});
