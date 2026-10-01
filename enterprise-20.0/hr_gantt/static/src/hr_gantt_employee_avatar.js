import { Avatar } from "@mail/views/web/fields/avatar/avatar";

export class GanttEmployeeAvatar extends Avatar {
    static template = "hr.GanttEmployeeAvatar";

    openCard(ev) {
        if (this.uiService.isSmall || !this.props.resId) {
            return;
        }
        const target = ev.currentTarget;
        if (!this.avatarCard.isOpen) {
            this.avatarCard.open(target, {
                id: this.props.resId,
                model: this.props.resModel,
            });
        }
    }
}
