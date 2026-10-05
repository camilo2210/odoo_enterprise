import { expect, test, click, mockFetch, waitUntil } from "@odoo/hoot";
import {
    defineModels,
    editSelectMenu,
    fields,
    mockService,
    models,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { TestOboxDevice } from "@obox/widgets/test_obox_device";

class OboxQueue extends models.Model {
    _name = "obox.queue";
    action_type = fields.Char();
    obox_id = fields.Integer();
    payload = fields.Json();
}
defineModels([OboxQueue]);

const setup = async (deviceType) => {
    const component = await mountWithCleanup(TestOboxDevice, {
        props: {
            record: {
                data: {
                    name: "Mock device",
                    identifier: "mock_device",
                    type: deviceType,
                    local_ip: "1.2.3.4",
                    obox_id: { id: 1 },
                },
            },
        },
    });
    const notificationsReceived = [];
    mockService("notification", {
        add: (message) => notificationsReceived.push(message),
    });

    return { component, notificationsReceived };
};

const mockScaleFetch = (result) => {
    mockFetch((url, options) => {
        const body = JSON.parse(options.body);
        const method = options?.method ?? "GET";
        if (
            url === "http://1.2.3.4/usb/v1/scale/read_scale_weight" &&
            method === "POST" &&
            body.identifier === "mock_device"
        ) {
            return result;
        }
    });
};

const mockCameraFetch = (result) => {
    mockFetch((url, options) => {
        const method = options?.method ?? "GET";
        if (
            url === "http://1.2.3.4/usb/v1/camera/take-picture?identifier=mock_device" &&
            method === "GET"
        ) {
            return result;
        }
    });
};

const mockReceiptFetch = (result) => {
    mockFetch((url, options) => {
        const method = options?.method ?? "GET";
        if (
            url === "http://1.2.3.4/usb/v1/printer/mock_device/cgi-bin/epos/service.cgi" &&
            method === "POST"
        ) {
            return result;
        }
    });
};

const waitForLoading = async (component) => {
    await waitUntil(() => !component.state.loading);
};

test("displays scale weight", async () => {
    const { notificationsReceived, component } = await setup("scale");
    mockScaleFetch({ weight: 1.234 });

    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Scale reads 1.234kg");
});

test("displays scale error", async () => {
    const { notificationsReceived, component } = await setup("scale");
    mockScaleFetch({ error: "Mock Error" });

    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Error reading scale: Mock Error");
});

test("displays camera image", async () => {
    const { component } = await setup("camera");
    mockCameraFetch({ image: "mockImage" });
    const openedFiles = [];
    component.fileViewer.open = (file) => openedFiles.push(file);

    await click(".btn");
    await waitForLoading(component);

    expect(openedFiles).toHaveLength(1);
    expect(openedFiles[0]).toEqual({
        defaultSource: "data:image/jpeg;base64,mockImage",
        downloadUrl: "data:image/jpeg;base64,mockImage",
        isImage: true,
        isViewable: true,
        name: "image.jpg",
    });
});

test("displays camera error", async () => {
    const { notificationsReceived, component } = await setup("camera");
    mockCameraFetch({ error: "Mock Error" });

    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Error taking photo: Mock Error");
});

test("displays network error", async () => {
    const { notificationsReceived, component } = await setup("scale");
    mockFetch(() => {
        throw new TypeError("Network Error");
    });

    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Failed to reach device");
});

test("sends test receipt print", async () => {
    const { notificationsReceived, component } = await setup("printer");
    mockReceiptFetch("mock-epos-response");

    await editSelectMenu(".o_select_menu input", { value: "Receipt" });
    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Test print successful");
});

test("sends test ZPL print", async () => {
    const { notificationsReceived, component } = await setup("printer");

    await editSelectMenu(".o_select_menu input", { value: "ZPL label" });
    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Test print successful");
    const queueRecord = OboxQueue.definition[0];
    const expectedPayload = btoa("^XA^FO50,50^ADN,36,20^FDTest ZPL label^FS^XZ");
    expect(queueRecord.payload).toEqual({
        method: "POST",
        url: "/usb/v1/printer/print",
        payload: { identifier: "mock_device", document: expectedPayload },
    });
});

test("sends test PDF print", async () => {
    const { notificationsReceived, component } = await setup("printer");
    onRpc("/report/download", () => "mock-pdf-response");

    await editSelectMenu(".o_select_menu input", { value: "PDF report" });
    await click(".btn");
    await waitForLoading(component);

    expect(notificationsReceived).toHaveLength(1);
    expect(notificationsReceived[0]).toBe("Test print successful");
    const queueRecord = OboxQueue.definition[0];
    expect(queueRecord.payload).toEqual({
        method: "POST",
        url: "/usb/v1/printer/print",
        payload: { identifier: "mock_device", document: btoa("mock-pdf-response") },
    });
});
