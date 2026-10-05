import {
    MAIN_EMBEDDINGS,
    READONLY_MAIN_EMBEDDINGS,
} from "@html_editor/others/embedded_components/embedding_sets";
import { user } from "@web/core/user";
import { aiVoiceTranscriptionEmbeddedComponent } from "./core/voice_transcription";
import { aiReadonlyVoiceTranscriptionEmbeddedComponent } from "./core/readonly_voice_transcription";

// If the user is an internal user, we use the editable version of the voice transcription embedded component,
// otherwise we use the readonly component.
// NOTE: "readonly" component used inside the editor will still allow editing text content of the component,
// Thanks to the editable descendents concept.
MAIN_EMBEDDINGS.push(
    user.isInternalUser
        ? aiVoiceTranscriptionEmbeddedComponent
        : aiReadonlyVoiceTranscriptionEmbeddedComponent
);
READONLY_MAIN_EMBEDDINGS.push(aiReadonlyVoiceTranscriptionEmbeddedComponent);
