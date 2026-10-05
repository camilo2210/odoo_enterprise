import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { Component, onWillStart, onWillUnmount, proxy, t, useProps } from "@odoo/owl";
import { useBus, useService } from "@web/core/utils/hooks";
import { BarcodeDialog } from "@web/core/barcode/barcode_dialog";
import { BarcodeInput } from "@barcodes/components/barcode_input";
import { url } from "@web/core/utils/urls";

const { DateTime } = luxon;

class MembersBarcodeInput extends BarcodeInput {
    static template = "frontdesk_partnership.MembersBarcodeInput";
}

export class WelcomePageMembers extends Component {
    static template = "frontdesk_partnership.WelcomePageMembers";
    static components = { MembersBarcodeInput };

    props = useProps({
        companyName: t.string(),
        createVisitor: t.function(),
        currentLang: t.string(),
        langs: t.or([t.object(), t.boolean()]),
        onChangeLang: t.function(),
        token: t.string(),
        resetData: t.function(),
        setVisitorData: t.function(),
        showScreen: t.function(),
        stationInfo: t.object(),
    });

    setup() {
        this.barcodeService = useService("barcode");
        this.dialogService = useService("dialog");
        this.props.resetData();
        this.state = proxy({
            today: this.getCurrentTime(),
        });
        this.timeInterval = setInterval(() => (this.state.today = this.getCurrentTime()), 1000);
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) =>
            this._onBarcodeScanned(ev.detail.barcode)
        );
        onWillStart(this.onWillStart);
        onWillUnmount(() => clearInterval(this.timeInterval));
    }

    async onWillStart() {
        const fileExtension = new Audio().canPlayType("audio/ogg") ? "ogg" : "mp3";
        this.sounds = {
            error: new Audio(url(`/barcodes/static/src/audio/error.${fileExtension}`)),
            success: new Audio(
                url(`/frontdesk_partnership/static/src/audio/success.${fileExtension}`)
            ),
        };
        this.sounds.error.load();
        this.sounds.success.load();
    }

    playSound(type) {
        type = type || "error";
        this.sounds[type].currentTime = 0;
        this.sounds[type].play();
    }

    getCurrentTime() {
        return DateTime.now().toLocaleString(DateTime.TIME_SIMPLE);
    }

    openManualBarcodeDialog() {
        this.dialogService.add(BarcodeDialog, {
            facingMode: "environment",
            onResult: (barcode) => {
                this.barcodeService.bus.trigger("barcode_scanned", { barcode });
            },
            onError: () => {},
        });
    }

    async _onBarcodeScanned(barcode) {
        var partnerValues;
        try {
            partnerValues = await rpc(
                `/frontdesk/${this.props.stationInfo.id}/${this.props.token}/get_visitor_data`,
                {
                    barcode: barcode,
                }
            );
        } catch (error) {
            this.playSound("error");
            throw error;
        }
        if (partnerValues) {
            this.props.setVisitorData(
                partnerValues.name,
                partnerValues.phone || false,
                partnerValues.email || false,
                partnerValues.company || false
            );
            this.dialogService.closeAll();
            this.playSound("success");
            this.props.showScreen("RegisterPage");
        }
        return barcode;
    }
}

registry.category("frontdesk_screens").add("WelcomePageMembers", WelcomePageMembers);
