import { patch } from "@web/core/utils/patch";
import { IotHttpService, iotHttpService } from "@iot/network_utils/iot_http_service";
import { rpc } from "@web/core/network/rpc";
import { location } from "@web/core/browser/browser";

patch(IotHttpService.prototype, {
    async getIotBoxData(iotBoxId) {
        const access_token = new URLSearchParams(location.search).get("access_token");
        const record = await rpc("/pos-self-order/get-iot-box-data/", {
            access_token,
            iot_box_id: iotBoxId,
        });
        if (record.error) {
            throw new Error(record.error);
        }
        return record;
    },
    /**
     * Mobile self ordering doesn't have access to local network.
     * We remove Longpolling from the connection types to avoid errors
     * when trying to connect to the IoT Box.
     */
    disableLocalNetwork() {
        this.connectionTypes = [this._websocket.bind(this)];
    },
});

patch(iotHttpService, {
    dependencies: iotHttpService.dependencies.filter((dep) => dep !== "orm"),
    _getMethodsToExpose(iotHttp, longpollingService, websocketService) {
        const disableLocalNetwork = iotHttp.disableLocalNetwork.bind(iotHttp);

        return {
            ...super._getMethodsToExpose(iotHttp, longpollingService, websocketService),
            disableLocalNetwork,
        };
    },
});
