declare module "models" {
    import { HelpdeskTicket as HelpdeskTicketClass } from "@website_helpdesk_livechat/core/common/helpdesk_ticket_model";

    export interface HelpdeskTicket extends HelpdeskTicketClass {}

    export interface Store {
        has_access_create_ticket: boolean;
        "helpdesk.ticket": StaticMailRecord<HelpdeskTicket, typeof HelpdeskTicketClass>;
        helpdesk_livechat_active: boolean|undefined;
    }

    export interface Models {
        "helpdesk.ticket": HelpdeskTicket;
    }
}
