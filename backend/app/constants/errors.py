ERROR_CODES = {
    'PROPERTY_NOT_FOUND': 'PROPERTY_NOT_FOUND',
    'BOOKING_CONFLICT': 'BOOKING_CONFLICT',
    'REPAIR_INVALID': 'REPAIR_INVALID',
    'USER_NOT_FOUND': 'USER_NOT_FOUND',
    'LEASE_INVALID': 'LEASE_INVALID',
    'TICKET_NOT_FOUND': 'TICKET_NOT_FOUND',
    'TICKET_STATE_CONFLICT': 'TICKET_STATE_CONFLICT',
    'TICKET_FORBIDDEN': 'TICKET_FORBIDDEN',
    'STAFF_NOT_FOUND': 'STAFF_NOT_FOUND',
    'STAFF_UNQUALIFIED': 'STAFF_UNQUALIFIED',
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'UNAUTHORIZED': 'UNAUTHORIZED',
    'FORBIDDEN': 'FORBIDDEN',
    'INTERNAL_ERROR': 'INTERNAL_ERROR',
}


class BizError(Exception):
    """业务异常，由统一异常处理器转换为标准响应。"""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
