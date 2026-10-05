declare module "models" {
    import { Call as CallClass } from "@voip/core/common/call_model";

    export interface Call extends CallClass {}

    export interface Activity {
        partner: ResPartner;
        phone: string|undefined;
        phone_country_id: Country;
    }
    export interface ResPartner {
        jobDescription: Readonly<unknown>;
        phone_country_id: Country;
        t9_name: string|undefined;
        voipName: Readonly<string>;
    }
    export interface ResUsers {
        should_display_in_call_im_status: boolean|undefined;
    }
    export interface ResUsersSettings {
        do_not_disturb_until_dt: import("luxon").DateTime;
        external_device_number: string;
        how_to_call_on_mobile: "ask" | "voip" | "phone";
        resetDoNotDisturbTimeoutId: number;
        should_call_from_another_device: boolean;
        voip_secret: string;
        voip_username: string;
    }
    export interface Store {
        resCountry: ReturnType<Store['makeCachedFetchData']>;
        "voip.call": StaticMailRecord<Call, typeof CallClass>;
        voipConfig: object|undefined;
    }

    export interface Models {
        "voip.call": Call;
    }
}
