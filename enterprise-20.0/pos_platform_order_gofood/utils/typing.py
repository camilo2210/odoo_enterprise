from typing import Any, Literal, NotRequired, TypedDict


class GoFoodSuccessResponse(TypedDict):
    success: Literal[True]
    data: dict[str, Any] | None


class GoFoodError(TypedDict):
    message_title: str
    message: str
    data: NotRequired[dict[str, Any] | None]


class GoFoodErrorResponse(TypedDict):
    success: Literal[False]
    errors: list[GoFoodError]


GoFoodResponse = GoFoodSuccessResponse | GoFoodErrorResponse
