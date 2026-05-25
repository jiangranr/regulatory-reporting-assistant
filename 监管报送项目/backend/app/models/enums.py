from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "UPLOADED"
    PARSED = "PARSED"
    FAILED = "FAILED"


class TaskStatus(StrEnum):
    CREATED = "CREATED"
    RULE_EXTRACTED = "RULE_EXTRACTED"
    IMPACT_ANALYZED = "IMPACT_ANALYZED"
    TICKET_GENERATED = "TICKET_GENERATED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SeverityLevel(StrEnum):
    L1_TRIVIAL = "L1"
    L2_LIGHT = "L2"
    L3_STANDARD = "L3"
    L4_MAJOR = "L4"


class ChangeTicketType(StrEnum):
    """母单类型：按监管变更场景划分。"""

    REPORT_ONBOARDING = "REPORT_ONBOARDING"           # 报表新增
    REPORT_REVISION = "REPORT_REVISION"               # 报表修订（结构/行列调整）
    SCOPE_ADJUSTMENT = "SCOPE_ADJUSTMENT"             # 修订范围/口径调整
    INDICATOR_ADD = "INDICATOR_ADD"                   # 现有报表新增指标
    VALIDATION_CHANGE = "VALIDATION_CHANGE"           # 校验规则变更
    INSTITUTION_FREQ_CHANGE = "INSTITUTION_FREQ_CHANGE"  # 机构范围/频度调整
    REPORT_DECOMMISSION = "REPORT_DECOMMISSION"       # 报表停报
    MANUAL_REVIEW = "MANUAL_REVIEW"                   # 拿不准，人工复核


class ActionTicketType(StrEnum):
    """子单类型：按责任团队×处理动作划分。"""

    SCOPE_CONFIRM = "SCOPE_CONFIRM"                   # 口径确认（业务）
    DATA_MAPPING = "DATA_MAPPING"                     # 数据映射（数据治理）—基于存量血缘
    LINEAGE_BUILD = "LINEAGE_BUILD"                   # 血缘建链（数据治理）—从零建立
    CATALOG_INIT = "CATALOG_INIT"                     # 报送目录初始化（报送管理）
    SOURCE_SYSTEM_CHANGE = "SOURCE_SYSTEM_CHANGE"     # 源系统改造（源系统团队）
    REPORT_PROCESSING = "REPORT_PROCESSING"           # 报送加工（数据开发）
    VALIDATION_RULE = "VALIDATION_RULE"               # 校验规则（数据质量）
    HISTORICAL_DATA = "HISTORICAL_DATA"               # 历史数据处理（业务+数据开发联签）
    TASK_INIT = "TASK_INIT"                           # 报送任务初始化（报送管理）
    TEST_ACCEPTANCE = "TEST_ACCEPTANCE"               # 测试验收（测试+业务）
    ARCHIVE_REVIEW = "ARCHIVE_REVIEW"                 # 归档复盘（报送管理）
    MERGED_LIGHTWEIGHT = "MERGED_LIGHTWEIGHT"         # L1 微调用：合并工单


class ResponsibleRole(StrEnum):
    BUSINESS = "BUSINESS"                             # 业务条线
    REPORTING_MGMT = "REPORTING_MGMT"                 # 报送管理岗
    DATA_GOVERNANCE = "DATA_GOVERNANCE"               # 数据治理
    SOURCE_SYSTEM = "SOURCE_SYSTEM"                   # 源系统团队
    DATA_DEV = "DATA_DEV"                             # 数据开发
    DATA_QUALITY = "DATA_QUALITY"                     # 数据质量
    QA = "QA"                                         # 测试
    COMPLIANCE = "COMPLIANCE"                         # 合规
