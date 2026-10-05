import { Component, useProps, proxy, t, xml } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { uuid } from "@web/core/utils/strings";

const iotBoxType = t.object({
    id: t.number(),
    ip: t.string(),
    identifier: t.string(),
    name: t.string(),
    use_lna: t.boolean(),
});

const iotDeviceType = t.object({
    id: t.number(),
    iot_id: iotBoxType,
    identifier: t.string(),
    name: t.string(),
});

class StatusIcon extends Component {
    props = useProps({ status: t.string() });
    static template = xml`
        <t t-if="this.props.status === 'loading'">
            <i class="oi oi-spin oi-fw" data-icon="progress_activity" />
        </t>
        <t t-elif="this.props.status === 'success'">
            <i class="oi oi-fw text-success" data-icon="check" />
        </t>
        <t t-else="">
            <i class="oi oi-fw text-danger" data-icon="close" />
        </t>
    `;
}

export class IotTestDialog extends Component {
    static template = "pos_iot.IotTestDialog";
    static components = { Dialog, StatusIcon };
    props = useProps({
        iotDevices: t.array(iotDeviceType),
    });

    setup() {
        this.iotHttp = useService("iot_http");
        const initialDeviceStatus = Object.fromEntries(
            this.props.iotDevices.map((device) => [device.id, "loading"])
        );
        const initialBoxStatus = Object.fromEntries(
            this.iotBoxes.entries().map(([iotBox]) => [
                iotBox.id,
                {
                    longpolling: "loading",
                    websocket: "loading",
                    localNetworkSpeed: null,
                    internetSpeed: null,
                },
            ])
        );
        this.startTime = new Date();
        this.deviceStatus = proxy(initialDeviceStatus);
        this.boxStatus = proxy(initialBoxStatus);
        this.testIotBoxes();
        this.testIotDevices();
    }

    get iotBoxes() {
        return new Set(this.props.iotDevices.map((device) => device.iot_id));
    }

    get iotDevicesByBox() {
        return Map.groupBy(this.props.iotDevices, (device) => device.iot_id);
    }

    /** @param {typeof iotBoxType} iotBox */
    async testIotBox(iotBox) {
        const requestId = uuid();
        try {
            await this.iotHttp.longpolling.sendMessage(
                iotBox.ip,
                {
                    device_identifier: iotBox.identifier,
                    data: {},
                },
                requestId,
                true,
                iotBox.use_lna
            );
            this.boxStatus[iotBox.id].longpolling = "success";
        } catch {
            this.boxStatus[iotBox.id].longpolling = "error";
        }

        this.iotHttp.websocket.onMessage(
            iotBox.identifier,
            iotBox.identifier,
            ({ result }) => {
                this.boxStatus[iotBox.id].websocket = "success";
                this.boxStatus[iotBox.id].localNetworkSpeed = result.lan_quality;
                this.boxStatus[iotBox.id].internetSpeed = result.wan_quality;
            },
            () => (this.boxStatus[iotBox.id].websocket = "error"),
            undefined,
            requestId
        );
        await this.iotHttp.websocket.sendMessage(
            iotBox.identifier,
            {},
            requestId,
            "test_connection"
        );
    }

    /** @param {typeof iotDeviceType} iotDevice */
    async testIotDevice(iotDevice) {
        const { promise, resolve } = Promise.withResolvers();
        await this.iotHttp.action(
            iotDevice.iot_id.id,
            iotDevice.identifier,
            {
                action: "status",
            },
            resolve,
            resolve
        );
        return promise;
    }

    testIotBoxes() {
        for (const iotBox of this.iotBoxes) {
            this.testIotBox(iotBox);
        }
    }

    testIotDevices() {
        for (const device of this.props.iotDevices) {
            this.testIotDevice(device).then(({ status }) => {
                this.deviceStatus[device.id] = status;
            });
        }
    }
}
