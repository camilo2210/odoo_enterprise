import { Component, computed, onMounted, onWillUnmount, useProps, signal, t } from "@odoo/owl";

export class AudioVisualizer extends Component {
    static template = "ai.AudioVisualizer";
    props = useProps({
        frequencies: t.instanceOf(Uint8Array),
        maxHeight: t.number().optional(32),
    });

    barsWrapperRef = signal.ref();
    barCount = signal(0)
    barHeights = computed(() =>  this.downsampleFrequencies(this.props.frequencies, this.barCount()));

    setup() {
        super.setup();

        this.resizeObserver = new ResizeObserver((entries) => {
            for (const entry of entries) {
                // The computation here results from the following formula
                // 4 * (n-1) + 3n + 8 = width
                // where 4 is the size of the gap between bars in pixels (corresponds to gap-1),
                // 3 the width of each bar,
                // 8 the summed horizontal padding of the component (px-1 class),
                // and n the number of bars.
                //
                // By simplifying we obtain:
                // 7n + 4 = width
                // and then n = (width - 4) / 7
                this.barCount.set(Math.floor((entry.borderBoxSize[0].inlineSize * 0.9 - 4) / 7));
            }
        });

        onMounted(() => {
            this.resizeObserver.observe(this.barsWrapperRef());
        });

        onWillUnmount(() => {
            this.resizeObserver.unobserve(this.barsWrapperRef());
        });
    }

    /**
     * Downsamples the frequencies array from frequencies.length to outputLength
     *
     * @param {Uint8Array} frequencies frequencies to downsample
     * @param {number} outputLength the length to downsample the frequencies array to
     * @return {Uint8Array} the downsampled array
     */
    downsampleFrequencies(frequencies, outputLength) {
        if (frequencies.length <= outputLength) {
            return frequencies;
        }
        const rateRatio = frequencies.length / outputLength;
        const outputFrequencies = new Float32Array(outputLength);

        let binCount = 0;
        let outputIndex = 0;
        let currentValue = 0;

        for (let i = 0; i < frequencies.length; i++) {
            const currentOutputIndex = Math.floor(i / rateRatio);
            if (outputIndex !== currentOutputIndex) {
                const average = currentValue / binCount;
                outputFrequencies[currentOutputIndex] = (average / 255) * this.props.maxHeight;
                outputIndex = currentOutputIndex;

                currentValue = 0;
                binCount = 0;
            }
            binCount++;
            currentValue += frequencies[i];
        }

        if (binCount > 0) {
            const average = currentValue / binCount;
            outputFrequencies[outputIndex] = (average / 255) * this.props.maxHeight;
        }

        return outputFrequencies;
    }
}
