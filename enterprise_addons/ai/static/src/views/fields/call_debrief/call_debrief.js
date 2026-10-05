import { signal } from "@odoo/owl";

import { useHotkey } from "@web/core/hotkeys/hotkey_hook";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { formatFloatTime } from "@web/views/fields/formatters";

import { parseTimedText } from "@ai/views/fields/call_debrief/transcript_parser";
import { CallDebrief } from "@mail/views/fields/call_debrief/call_debrief";

const MIN_GAP_DURATION_SEC = 2;

patch(CallDebrief.prototype, {
    setup() {
        super.setup(...arguments);
        this.transcriptContainer = signal.ref();
        this.highlightedLineRef = null;
        this.isAutoScrollEnabled = true;

        Object.assign(this.state, {
            transcriptLines: [],
            plainTextTranscript: null,
        });

        useHotkey("arrowup", () => this._jumpToTranscriptLine(-1), {
            global: true,
            allowRepeat: true,
        });
        useHotkey("arrowdown", () => this._jumpToTranscriptLine(1), {
            global: true,
            allowRepeat: true,
        });
    },

    /**
     * @override
     */
    _getArtifactFields() {
        return [...super._getArtifactFields(), "is_stt", "transcript"];
    },

    /**
     * @override
     */
    _isPlaybackArtifact(art) {
        return super._isPlaybackArtifact(art) && !art.is_stt;
    },

    /**
     * @override
     */
    async _loadData(props) {
        const initialResId = props.record.resId;
        const artifacts = await super._loadData(props);

        if (this.activeResId !== initialResId) {
            return;
        }

        if (!artifacts || !artifacts.length) {
            this.state.transcriptLines = [];
            this.state.plainTextTranscript = null;
            return;
        }

        const allTranscriptLines = [];
        let plainText = "";

        for (const art of artifacts) {
            const startSec = art.start_ms / 1000;
            if (art.transcript) {
                if (this._getTranscriptType(art.transcript) === "timed") {
                    allTranscriptLines.push(
                        ...this._buildTranscriptLines(art.transcript, startSec)
                    );
                } else {
                    plainText += (plainText ? "\n\n" : "") + art.transcript.trim();
                }
            }
        }
        allTranscriptLines.sort((a, b) => a.startSecRelToCall - b.startSecRelToCall);
        this.state.transcriptLines = allTranscriptLines;
        this.state.plainTextTranscript = plainText || null;
    },

    /**
     * @override
     */
    setPlaybackTime(options = {}) {
        // Any seek operation (timeline click) re-enables auto-scroll
        this.isAutoScrollEnabled = true;
        super.setPlaybackTime(options);
        this.alignTranscript();
    },

    /**
     * @override
     */
    onTimeUpdate(ev) {
        super.onTimeUpdate(ev);
        this.alignTranscript();
    },

    /**
     * @override
     */
    togglePlay() {
        // Playing also re-enables auto-scroll if it was disabled
        if (!this.state.isPlaying) {
            this.isAutoScrollEnabled = true;
        }
        super.togglePlay();
    },

    // --- Transcript Specific Methods ---

    /**
     * @override
     */
    get hasTimeline() {
        return super.hasTimeline || this.hasTranscriptLines;
    },

    /**
     * @override
     */
    get callDebriefCustomClasses() {
        return this.hasTranscript && this.hasVideo ? ' o-CallDebrief--has-video-transcript' : '';
    },

    get hasTranscriptLines() {
        return this.state.transcriptLines.length > 0;
    },

    get hasPlainTextTranscript() {
        return Boolean(this.state.plainTextTranscript);
    },

    get hasTranscript() {
        return this.hasTranscriptLines || this.hasPlainTextTranscript;
    },

    _buildTranscriptLines(transcriptText, offsetSec) {
        let lastEndSec = 0;

        return parseTimedText(transcriptText).flatMap((line) => {
            const startSecRelToCall = offsetSec + line.startSec;
            const endSecRelToCall = offsetSec + line.endSec;
            const result = [];

            // Detect gaps
            if (lastEndSec > 0 && startSecRelToCall - lastEndSec > MIN_GAP_DURATION_SEC) {
                result.push({
                    isGap: true,
                    startSecRelToCall: lastEndSec,
                    duration: startSecRelToCall - lastEndSec,
                });
            }

            result.push({
                ...line,
                startSecRelToCall,
                endSecRelToCall,
                isGap: false,
                isActive: false,
                isHovered: false,
            });

            lastEndSec = endSecRelToCall;
            return result;
        });
    },

    _getTranscriptType(transcriptText) {
        return transcriptText.includes("-->") ? "timed" : "plaintext";
    },

    formatDuration(seconds) {
        const formatted = formatFloatTime(seconds || 0, {
            unit: "seconds",
            showSeconds: true,
            numeric: true,
        });
        if (this.callDurationSeconds < 3600) {
            return formatted.slice(2);
        }
        return formatted;
    },

    formatSilence(duration) {
        return _t("silence (%(duration)s)", { duration: this.formatDuration(duration) });
    },

    /**
     * Highlights and auto-scrolls the transcript to match the current playback time.
     */
    alignTranscript() {
        if (!this.hasTranscriptLines) {
            return;
        }

        const transcriptLines = this.state.transcriptLines;
        const closestLine = this.state.transcriptLines.findLast(
            (line) => line.startSecRelToCall <= this.state.currentTime
        );

        if (closestLine && !closestLine.isGap) {
            const lineElement = this.transcriptContainer()?.querySelector(
                `[data-timestamp="${closestLine.startSecRelToCall}"]`
            );
            if (lineElement) {
                this._highlightTranscriptLineAndMarker(transcriptLines, closestLine, lineElement);

                if (this.isAutoScrollEnabled) {
                    this._scrollTranscriptToLine(lineElement);
                }
                return;
            }
        }

        this._clearTranscriptHighlight();
    },

    /**
     * Highlights the closest transcript line and its associated marker,
     * deactivating all other lines in the process.
     *
     * @param {Array} transcriptLines - Array of transcript line.
     * @param {Object} closestLine - The transcript line object to mark as active.
     * @param {HTMLElement} lineElement - The DOM element corresponding to the highlighted line.
     */
    _highlightTranscriptLineAndMarker(transcriptLines, closestLine, lineElement) {
        for (const line of transcriptLines) {
            line.isActive = (line === closestLine);
        }
        this.highlightedLineRef = lineElement;
    },

    _clearTranscriptHighlight() {
        const lines = this.state.transcriptLines;
        const hasActiveLine = lines.some(line => line.isActive === true);

        if (hasActiveLine) {
            for (const line of lines) {
                line.isActive = false;
            }
        }
        if (this.highlightedLineRef) {
            this.highlightedLineRef = null;
        }
    },

    _scrollTranscriptToLine(lineElement) {
        const container = this.transcriptContainer();
        if (!container || !lineElement) {
            return;
        }
        const top =
            lineElement.offsetTop - container.offsetHeight / 2 + lineElement.offsetHeight / 2;
        container.scrollTo({ top, behavior: "smooth" });
    },

    _getHighlightedLineIndex() {
        if (!this.highlightedLineRef) {
            return -1;
        }
        const highlightedTimestamp = parseFloat(this.highlightedLineRef.dataset.timestamp);
        return this.state.transcriptLines.findIndex(
            (line) => Math.abs(line.startSecRelToCall - highlightedTimestamp) < 0.001
        );
    },

    onTranscriptLineMouseEnter(line) {
        line.isHovered = true;
    },

    onTranscriptLineMouseLeave(line) {
        line.isHovered = false;
    },

    onTranscriptLineClick(line) {
        this.isAutoScrollEnabled = true;
        this.setPlaybackTime({ timestamp: line.startSecRelToCall });
    },

    _jumpToTranscriptLine(offset) {
        if (!this.hasTranscriptLines) {
            return;
        }

        const currentLineIndex = this._getHighlightedLineIndex();
        let targetIndex = -1;

        if (currentLineIndex === -1) {
            targetIndex = offset > 0 ? 0 : this.state.transcriptLines.length - 1;
        } else {
            targetIndex = currentLineIndex + offset;
            while (
                targetIndex >= 0 &&
                targetIndex < this.state.transcriptLines.length &&
                this.state.transcriptLines[targetIndex].isGap
            ) {
                targetIndex += offset;
            }
        }

        if (targetIndex >= 0 && targetIndex < this.state.transcriptLines.length) {
            const targetLine = this.state.transcriptLines[targetIndex];
            this.skipNextTimeUpdate = true;
            this.isAutoScrollEnabled = true;
            this.setPlaybackTime({ timestamp: targetLine.startSecRelToCall });
        }
    },
});
