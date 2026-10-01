export class Ringtone {
    static dial = { src: "/voip/static/ringtones/dialtone.mp3", volume: 0.7 };
    static incoming = { src: "/voip/static/ringtones/incomingcall.mp3" };
    static ringback = { src: "/voip/static/ringtones/ringbacktone.mp3" };

    /** @type {HTMLAudioElement} */
    audio = Object.assign(new Audio(), { loop: true });

    /**
     * Plays the corresponding ringtone.
     *
     * @param {("dial"|"incoming"|"ringback")} ringtone - Name of the ringtone to be played.
     */
    play(ringtone) {
        Object.assign(this.audio, Ringtone[ringtone]);
        this.audio.currentTime = 0;
        this.audio.load();
        this.audio.play().catch(() => console.warn("Ringtone playback prevented."));
    }

    stop() {
        this.audio.pause();
        this.audio.removeAttribute("src"); // prevent media keys from resuming playback
        this.audio.load();
    }
}
