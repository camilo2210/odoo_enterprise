declare module "models" {
    export interface DiscussChannel {
        whatsapp_partner_id: ResPartner;
        whatsappMember: ChannelMember;
    }
    export interface Message {
        whatsappStatus: string|undefined;
    }
}
