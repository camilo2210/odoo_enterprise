declare module "services" {
    import { iotLongpollingService } from "@iot/network_utils/iot_longpolling";
    import { iotHttpService } from "@iot/network_utils/iot_http_service";

    export interface Services {
        iot_longpolling: typeof iotLongpollingService;
        iot_http: typeof iotHttpService;
    }
}
