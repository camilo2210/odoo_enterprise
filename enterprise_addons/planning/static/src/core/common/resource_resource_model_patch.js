import { patch } from "@web/core/utils/patch";
import { fields } from "@mail/model/misc";
import { ResourceResource } from "@resource_mail/core/common/resource_resource_model";

patch(ResourceResource.prototype, {
    setup() {
        super.setup();
        this.default_role_id = fields.One("planning.role");
        this.role_ids = fields.Many("planning.role");
    },
});
