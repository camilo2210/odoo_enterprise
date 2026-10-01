declare module "models" {
    import { WhatsAppAccount as WhatsAppAccountClass } from "@whatsapp/core/common/whatsapp_account_model";

    export interface WhatsAppAccount extends WhatsAppAccountClass {}

    export interface Composer {
        threadExpired: boolean;
    }
    export interface DiscussChannel {
        wa_account_id: WhatsAppAccount;
        whatsapp_channel_blocked: boolean;
        whatsapp_channel_valid_until: import("luxon").DateTime;
    }
    export interface Store {
        "whatsapp.account": StaticMailRecord<WhatsAppAccount, typeof WhatsAppAccountClass>;
    }
    export interface Thread {
        canSendWhatsapp: boolean|undefined;
    }

    export interface Models {
        "whatsapp.account": WhatsAppAccount;
    }
}
