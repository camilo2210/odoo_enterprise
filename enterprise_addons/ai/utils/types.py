from typing import Any, Literal, NotRequired, TypedDict


class TextPart(TypedDict):
    type: Literal['text']
    text: str
    sources: NotRequired[Any]
    provider_data: NotRequired[dict[str, Any]]


class InlineDataPart(TypedDict):
    type: Literal['inline_data']
    data: Any
    mimetype: str
    metadata: NotRequired[dict[str, Any]]
    provider_data: NotRequired[dict[str, Any]]


AIMessageParts = list[TextPart | InlineDataPart]


class ToolCallPart(TypedDict):
    type: Literal['tool_call']
    name: str
    args: Any
    call_id: Any
    provider_data: NotRequired[dict[str, Any]]


class ToolResultPart(TypedDict):
    type: Literal['tool_result']
    tool_name: str
    tool_call_id: str
    result: AIMessageParts
    success: bool


class UserMessage(TypedDict):
    role: Literal['user']
    content: list[TextPart | InlineDataPart | ToolResultPart]


class AssistantMessage(TypedDict):
    role: Literal['assistant']
    content: list[TextPart | InlineDataPart | ToolCallPart]
    provider_metadata: dict[str, Any]


Message = UserMessage | AssistantMessage


class CompletionOptions(TypedDict):
    schema: NotRequired[dict[str, Any]]
    web_grounding: NotRequired[bool]
    aspect_ratio: NotRequired[str]
    usage: NotRequired[str]
    image_generation: NotRequired[bool]
    boost_reasoning: NotRequired[bool]


ToolSchemaType = Literal['string', 'number', 'integer', 'object', 'array', 'boolean', 'null']


class ToolSchema(TypedDict):
    type: ToolSchemaType | list[ToolSchemaType]
    required: list[str]
    items: NotRequired['ToolSchema | list[ToolSchema]']
    properties: NotRequired[dict[str, 'ToolSchema']]
    additionalProperties: NotRequired[bool]
    anyOf: NotRequired[list['ToolSchema']]


class Tool(TypedDict):
    name: str
    instructions: str
    schema: ToolSchema | None


class CompletionResponse(TypedDict):
    result: AssistantMessage


class CompletionSuccess(TypedDict):
    kind: Literal['success']
    message: AssistantMessage


class CompletionFailure(TypedDict):
    kind: Literal['failure']
    code: Literal['request_failed']


class SessionResponse(TypedDict):
    loop_state: Literal[
        'ready', 'waiting_model', 'waiting_confirmation', 'waiting_answer',
        'waiting_client_result', 'waiting_external_result', 'waiting_child',
    ]
    interactionConsumed: NotRequired[bool]


class PendingSkip(TypedDict):
    kind: Literal['skip']


class PendingConfirmation(TypedDict):
    kind: Literal['confirmation']
    value: str


class PendingQuestion(TypedDict):
    kind: Literal['question']
    value: list[str]


class PendingClientResult(TypedDict):
    kind: Literal['client_result']
    value: Any


class PendingClientError(TypedDict):
    kind: Literal['client_error']
    value: str


class PendingAsync(TypedDict):
    kind: Literal['async']
    call_id: str


PendingInteractionResponse = (
    PendingSkip | PendingConfirmation | PendingQuestion | PendingClientResult | PendingClientError | PendingAsync)


class EmbeddingInput(TypedDict):
    title: str
    content: str


class EmbeddingResponse(TypedDict):
    embeddings: list[list[float]]


class TranscriptionOptions(TypedDict):
    mimetype: NotRequired[str]
    response_format: NotRequired[str]


class TranscriptionResponse(TypedDict):
    result: str


class RealtimeTranscriptionResponse(TypedDict):
    session_token: str
    iap_transaction_token: str
