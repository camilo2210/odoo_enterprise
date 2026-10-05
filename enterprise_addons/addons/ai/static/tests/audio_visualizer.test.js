import { expect, test } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { Component, signal, xml } from "@odoo/owl";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { mountWithCleanup } from "@web/../tests/web_test_helpers";
import { AudioVisualizer } from "@ai/components/audio_visualizer/audio_visualizer";

defineMailModels();

function barHeights() {
    return [...document.querySelectorAll(".o-ai-audio-visualizer-bar")].map((bar) =>
        parseFloat(bar.style.height)
    );
}

test("audio visualizer bar heights reactively follow the frequencies prop", async () => {
    const frequencies = signal(new Uint8Array(128).fill(0));

    class Container extends Component {
        static components = { AudioVisualizer };
        static template = xml`
            <div style="width: 200px;">
                <AudioVisualizer frequencies="this.frequencies()" maxHeight="32"/>
            </div>`;
        setup() {
            this.frequencies = frequencies;
        }
    }

    await mountWithCleanup(Container);
    await animationFrame();
    await animationFrame();

    expect(barHeights().every((h) => h === 0)).toBe(true);

    frequencies.set(new Uint8Array(128).fill(255));
    await animationFrame();

    expect(barHeights().some((h) => h > 0)).toBe(true);
});
