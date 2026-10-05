import { Avatar } from "@mail/views/web/fields/avatar/avatar";
import { Component, onWillStart, useProps, proxy, t } from "@odoo/owl";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";

export class DocumentsGroupAvatarCardPopover extends Component {
    static template = "documents.DocumentsGroupAvatarCardPopover";
    static components = { Avatar };
    props = useProps({
        close: t.function(),
        userIds: t.object(),
    });

    setup() {
        this.orm = useService("orm");
        this.state = proxy({ users: [] });
        onWillStart(async () => {
            this.state.users = await this.orm.read("res.users", this.props.userIds.slice(0, 10), [
                "name",
                "email",
            ]);
        });
    }
}

export class DocumentsGroupAvatar extends Avatar {
    setup() {
        super.setup(...arguments);
        this.documentsProps = useProps({ userIds: t.array(t.number()) });
        this.avatarCard = usePopover(DocumentsGroupAvatarCardPopover);
    }

    get canOpenPopover() {
        return super.canOpenPopover && this.documentsProps.userIds.length;
    }

    get popoverProps() {
        return {
            userIds: this.documentsProps.userIds,
        };
    }
}
