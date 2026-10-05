import { rpc } from "@web/core/network/rpc";
import { useBus, useService } from "@web/core/utils/hooks";
import { Component, onWillStart } from "@odoo/owl";
import { BarcodeView } from "@barcodes/components/barcode_view";
import { url, redirect } from "@web/core/utils/urls";
import { post } from "@web/core/network/http_service";

export class StockBarcodeMainScanner extends Component {
    static components = { BarcodeView };
    static template = "stock_barcode.MainScanner";

    setup() {
        this.actionService = useService("action");
        this.dialogService = useService("dialog");
        this.pwaService = useService("pwa");
        this.uiService = useService("ui");
        this.home = useService("home_menu");
        this.notificationService = useService("notification");
        this.barcodeService = useService("barcode");
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) =>
            this._onBarcodeScanned(ev.detail.barcode)
        );

        onWillStart(async () => {
            const data = await rpc("/stock_barcode/get_main_menu_data");
            this.locationsEnabled = data.groups.locations;
            this.packageEnabled = data.groups.package;
            this.trackingEnabled = data.groups.tracking;
            this.quantCount = data.quant_count;
            this.soundEnable = data.play_sound;
            if (this.soundEnable) {
                const fileExtension = new Audio().canPlayType("audio/ogg; codecs=vorbis")
                    ? "ogg"
                    : "mp3";
                this.sounds = {
                    success: new Audio(
                        url(`/stock_barcode/static/src/audio/success.${fileExtension}`)
                    ),
                };
                this.sounds.success.load();
            }
        });
    }

    async logout() {
        const redirectPart = this.pwaService.isScopedApp ? "scoped_app" : "/odoo";
        const path = `/web/session/logout?redirect=${redirectPart}/barcode`;
        const url = await post(path, { csrf_token: odoo.csrf_token }, "url");
        redirect(url);
    }

    _onScannerResult(barcode) {
        this._onBarcodeScanned(barcode);
    }

    _onScannerError(error) {
        console.error(error);
    }

    playSound(soundName) {
        if (this.soundEnable) {
            this.sounds[soundName].currentTime = 0;
            this.sounds[soundName].play().catch((error) => {
                // `play` returns a promise. In case this promise is rejected (permission
                // issue for example), catch it to avoid Odoo's `UncaughtPromiseError`.
                this.soundEnable = false;
                console.warn(error);
            });
        }
    }

    async _onBarcodeScanned(barcode) {
        const res = await rpc("/stock_barcode/scan_from_main_menu", { barcode });
        if (res.action) {
            this.playSound("success");
            return this.actionService.doAction(res.action);
        }
        this.addNotification(res.warning, barcode);
    }

    addNotification(content, _barcode) {
        this.notificationService.add(content, { type: "danger" });
    }
}
