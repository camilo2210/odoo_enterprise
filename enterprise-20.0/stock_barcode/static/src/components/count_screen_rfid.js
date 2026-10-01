import { Component, onWillUnmount, proxy, t, useEffect, useProps } from "@odoo/owl";
import { session } from "@web/session";

export class CountScreenRFID extends Component {
    static template = "stock_barcode.CountScreenRFID";

    props = useProps({
        close: t.function(),
        receivedRFIDs: t.array(),
        totalRFIDs: t.array(),
    });

    setup() {
        this.state = proxy({
            duration: "00:00",
            readRate: 0,
        });
        this.delayBeforeStopRefreshRate = (session.time_between_reads_in_ms || 100) * 2;
        this.totalSeconds = 0;
        this.activeScanningTotalTime = 0;
        this.setActiveScanning();
        this.initialTimestamp = Date.now();
        this.timeInterval = setInterval(() => {
            const currentTimestamp = Date.now();
            const milliseconds = currentTimestamp - this.initialTimestamp;
            this.totalSeconds = Math.floor(milliseconds / 1000);
            const seconds = this.totalSeconds % 60;
            const minutes = Math.floor(this.totalSeconds / 60);
            const strSeconds = String(seconds).padStart(2, "0");
            const strMinutes = String(minutes).padStart(2, "0");
            this.state.duration = `${strMinutes}:${strSeconds}`;
        }, 1000);
        this.updateReadsRateInterval = setInterval(() => {
            if (this.activeScanning) {
                this.activeScanningTotalTime += 50;
            }
            const seconds = this.activeScanningTotalTime / 1000;
            const divider = Math.max(seconds, 1);
            this.state.readRate = Math.floor(this.props.receivedRFIDs.length / divider);
        }, 50);

        useEffect(() => {
            clearTimeout(this.activeScanningTimeout);
            this.setActiveScanning();
        });

        onWillUnmount(() => {
            clearInterval(this.updateReadsRateInterval);
            clearTimeout(this.activeScanningTimeout);
        });
    }

    setActiveScanning() {
        if (this.activeScanningTimeout) {
            clearTimeout(this.activeScanningTimeout);
        }
        this.activeScanning = true;
        this.activeScanningTimeout = setTimeout(() => {
            this.activeScanning = false;
        }, this.delayBeforeStopRefreshRate);
    }

    get totalRead() {
        return this.props.totalRFIDs.length;
    }

    get uniqueTags() {
        return new Set(this.props.totalRFIDs).size;
    }
}
