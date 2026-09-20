"""业务错误码与提示文案，统一维护。

格式：错误码 -> (默认 HTTP 状态码, 中文提示)
"""

ERROR_CODES = {
    # 通用
    'VALIDATION_ERROR': (400, '请求参数不合法'),
    'UNAUTHORIZED': (401, '未登录或登录已失效'),
    'FORBIDDEN': (403, '无权执行该操作'),
    'NOT_FOUND': (404, '资源不存在'),
    'CONFLICT': (409, '操作冲突，请刷新后重试'),

    # 房源 / 租约
    'HOUSE_NOT_FOUND': (404, '房屋不存在'),
    'NO_ACTIVE_LEASE': (403, '您在该房屋名下没有有效租约，不能报修'),

    # 报修工单
    'REPAIR_INVALID': (400, '报修信息不合法'),
    'TICKET_NOT_FOUND': (404, '报修工单不存在'),
    'TICKET_NOT_PENDING': (409, '工单不是待受理状态，不能接单'),
    'TICKET_NOT_PROCESSING': (409, '工单不是处理中状态，不能转派或完工'),
    'TICKET_COMPLETED': (409, '工单已完成，操作被拒绝'),
    'NOT_CURRENT_OWNER': (403, '只有当前责任人才能执行该操作'),
    'STAFF_NOT_QUALIFIED': (403, '该物业人员不具备此类故障的处理资质'),
    'NO_QUALIFIED_STAFF': (409, '当前没有可接单的合格物业人员'),
    'VISIT_TIME_INVALID': (400, '预计上门时间必须晚于当前时间'),
}
