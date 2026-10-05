import { imStatusDataRegistry } from "@mail/core/common/im_status";
import { _t } from "@web/core/l10n/translation";

imStatusDataRegistry.add(
    "whatsapp",
    {
        condition: ({ member }) => Boolean(member?.eq(member.channel_id.whatsappMember)),
        icon: "oi_whatsapp",
        iconClass: "text-success",
        title: _t("WhatsApp User"),
    },
    { sequence: 30 }
);
