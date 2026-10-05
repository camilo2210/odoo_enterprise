# Part of Odoo. See LICENSE file for full copyright and licensing details.


class McpException(Exception):
    code = -32603  # JSONRPC internal error

    def __init__(self, message, **extra_params):
        super().__init__(message)
        self.message = message
        self.extra_params = extra_params


class McpMethodNotFoundError(McpException):
    code = -32601

    def __init__(self):
        super().__init__("Method doesn't exist")
