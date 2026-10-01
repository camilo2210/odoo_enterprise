import { Store } from "@mail/core/common/store_service";

import { patch } from "@web/core/utils/patch";

patch(Store.prototype, {
    async getMessagePostParams({ postData }) {
        const params = await super.getMessagePostParams(...arguments);
        if (postData.account_reports_annotation_date) {
            params.context ??=  {};
            params.context.account_reports_annotation_date = postData.account_reports_annotation_date;
        }
        return params;
    },
});
