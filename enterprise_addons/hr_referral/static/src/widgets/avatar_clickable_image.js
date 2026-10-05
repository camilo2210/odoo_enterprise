import { ImageField, imageField } from "@web/views/fields/image/image_field";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";


export class AvatarClickableImage extends ImageField {
    static template = "hr_referral.AvatarClickableImage";

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.applicantId = this.props.record.resId;
    }

    async onClick() {
        this.actionService.doAction({
            type: 'ir.actions.client',
            tag: 'hr_referral_welcome',
            name: _t('Dashboard'),
            target: 'main',
            context: {
                choose_avatar: true,
                applicant_id: this.applicantId,
            },
        }, { noEmptyTransition: true });
    }

}

export const avatarClickableImage = {
    ...imageField,
    component: AvatarClickableImage,
};

registry.category("fields").add("avatarClickableImage", avatarClickableImage);
