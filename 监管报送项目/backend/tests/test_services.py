import json

from app.models.db_models import RegDocument
from app.services import document_profiler
from app.services.document_parser import parse_text_document


def test_parse_text_document_returns_content_and_excerpt():
    parsed = parse_text_document(
        filename="notice.txt",
        content="关于进一步支持境外机构投资者开展债券回购业务。资金收付应符合账户管理规定。".encode(
            "utf-8"
        ),
    )

    assert parsed.filename == "notice.txt"
    assert "境外机构投资者" in parsed.text
    assert parsed.excerpt.startswith("关于进一步支持")


def test_parse_text_document_returns_parse_metadata():
    parsed = parse_text_document(
        filename="notice.md",
        content="# 债券回购通知\n\n第一条 资金账户应保持一致。\n\n第二条 报送字段应完整。".encode(
            "utf-8"
        ),
    )

    assert parsed.parser == "text"
    assert parsed.char_count >= 30
    assert parsed.paragraph_count == 3
    assert parsed.quality == "GOOD"
    assert parsed.error_message == ""


def test_document_profile_without_1104_table_code_skips_full_analysis():
    document = RegDocument(
        filename="notice.txt",
        storage_path="/tmp/notice.txt",
        title="一般业务通知",
        parsed_text="支持相关机构开展业务，做好宣传和组织工作。",
        parse_quality="GOOD",
    )
    profile = document_profiler.generate_document_profile(document, {})

    assert profile.has_1104_reference is False
    assert profile.suggested_route == "SKIP"
    assert profile.should_create_task is False
    assert profile.affected_table_codes == []
    assert profile.confidence_score == 0.95


def test_document_profile_prompt_includes_only_found_1104_items():
    document = RegDocument(
        filename="notice.txt",
        storage_path="/tmp/notice.txt",
        title="G24口径调整通知",
        parsed_text="监管要求调整G24最大百家金融机构同业融入情况表中同业融入余额统计口径。",
        parse_quality="GOOD",
    )
    prompt = document_profiler._build_prompt(  # noqa: SLF001
        document,
        ["G24"],
        {
            "reporting_items": [
                {
                    "item_code": "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100",
                    "item_name": "最大百家金融机构同业融入余额",
                    "row_label": "金融机构同业融入",
                    "column_label": "余额",
                },
                {
                    "item_code": "G31.PART_I.BOND_INVESTMENT_BALANCE",
                    "item_name": "债券投资余额",
                    "row_label": "债券投资",
                    "column_label": "余额",
                },
            ]
        },
    )

    assert "发现的1104报表表号：G24" in prompt
    assert "G24.MAIN.INTERBANK_BORROWING_BAL_TOP100" in prompt
    assert "G31.PART_I.BOND_INVESTMENT_BALANCE" not in prompt
    assert "change_signals" in prompt


def test_document_profile_prompt_excludes_internal_revision_span_json():
    document = RegDocument(
        filename="notice.txt",
        storage_path="/tmp/notice.txt",
        title="G01_IV口径调整通知",
        parsed_text="\n".join(
            [
                "# 报表表样与填报说明联合导入",
                "",
                "## 当前版本修订动作（共 1 条）",
                "- [新增 | 陈施霖 | 2024-12-23] 金融机构",
                "",
                "## 当前版本原位修订片段（共 2 段）",
                '{"type": "TEXT", "text": "[11.a.2", "author": "", "date": "", "action": ""}',
                '{"type": "INSERT", "text": "金融机构", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "新增"}',
                "",
                "## 填报说明正文",
                "[11.a.2 通过第三方互联网平台吸收的个人活期存款]指项目 11.a 中，金融机构吸收的个人活期存款。",
            ]
        ),
        parse_quality="GOOD",
    )

    prompt = document_profiler._build_prompt(  # noqa: SLF001
        document,
        ["G01_IV"],
        {"reporting_items": []},
    )

    assert "当前版本原位修订片段" not in prompt
    assert '{"type": "TEXT"' not in prompt
    assert "当前版本修订动作" in prompt
    assert "[11.a.2 通过第三方互联网平台吸收的个人活期存款]" in prompt


def test_document_profile_prompt_includes_reporting_objects_and_sections():
    document = RegDocument(
        filename="notice.txt",
        storage_path="/tmp/notice.txt",
        title="G99新增报表通知",
        parsed_text="监管要求新增G99专项资金业务统计表第一部分大额同业业务。",
        parse_quality="GOOD",
    )

    prompt = document_profiler._build_prompt(  # noqa: SLF001
        document,
        ["G99"],
        {
            "reporting_objects": [
                {
                    "object_code": "G99",
                    "object_name": "专项资金业务统计表",
                    "object_category": "业务类报表",
                    "report_frequency": "季",
                }
            ],
            "reporting_sections": [
                {
                    "object_code": "G99",
                    "section_code": "PART_I",
                    "section_name": "第一部分：大额同业业务",
                    "display_order": 1,
                }
            ],
            "reporting_items": [],
        },
    )

    assert "系统维护的监管报表本体" in prompt
    assert "G99: 专项资金业务统计表" in prompt
    assert "G99.PART_I: 第一部分：大额同业业务" in prompt


def test_document_profile_in_scope_tables_come_from_reporting_objects(monkeypatch):
    document = RegDocument(
        filename="notice.txt",
        storage_path="/tmp/notice.txt",
        title="G99口径调整通知",
        parsed_text="监管要求调整G99专项资金业务统计表大额同业业务统计口径。",
        parse_quality="GOOD",
    )

    def fake_complete_json(messages):
        return (
            {
                "change_signals": [
                    {
                        "table_code": "G99",
                        "section_hint": "第一部分",
                        "indicator_hint": "大额同业业务",
                        "change_type": "SCOPE_ADJUST",
                        "evidence_text": "调整G99专项资金业务统计表大额同业业务统计口径。",
                        "confidence": 0.88,
                    }
                ],
                "reason": "命中数据库维护的G99报表范围。",
            },
            '{"ok": true}',
            "fake-model",
        )

    monkeypatch.setattr(document_profiler, "complete_json", fake_complete_json)

    profile = document_profiler.generate_document_profile(
        document,
        {
            "reporting_objects": [
                {
                    "object_code": "G99",
                    "object_name": "专项资金业务统计表",
                    "object_category": "业务类报表",
                    "report_frequency": "季",
                }
            ],
            "reporting_sections": [],
            "reporting_items": [],
        },
    )

    assert profile.in_scope_tables == ["G99"]
    assert profile.out_of_scope_tables == []
    assert profile.suggested_route == "FULL_ANALYSIS"
    assert profile.should_create_task is True


def test_document_profile_revision_insert_marker_with_formula_is_scope_adjustment():
    signals = document_profiler._parse_change_signals(  # noqa: SLF001
        {
            "change_signals": [
                {
                    "table_code": "G31",
                    "section_hint": "第 I 部分",
                    "indicator_hint": "C.修正久期填报定义/公式",
                    "change_type": "INSTRUCTION_ADJUST",
                    "evidence_text": (
                        "- [新增 | 陈施霖 | 2024-12-20] "
                        "衡量单笔债券或债券投资组合估值（价格）对到期收益率变化的敏感度指标，"
                        "计算公式为 MD=-(dP/P)/dy=D/(1+y/k)"
                    ),
                    "confidence": 0.95,
                }
            ]
        }
    )

    assert signals[0].change_type == "SCOPE_ADJUST"


def test_document_profile_revision_insert_marker_keeps_explicit_business_add():
    signals = document_profiler._parse_change_signals(  # noqa: SLF001
        {
            "change_signals": [
                {
                    "table_code": "G31",
                    "section_hint": "第 I 部分",
                    "indicator_hint": "C.修正久期",
                    "change_type": "INSTRUCTION_ADJUST",
                    "evidence_text": "- [新增 | 陈施霖 | 2024-12-20] 新增 C 列修正久期。",
                    "confidence": 0.95,
                }
            ]
        }
    )

    assert signals[0].change_type == "ADD"


def test_document_profile_merges_same_instruction_indicator_fragments():
    signals = document_profiler._parse_change_signals(  # noqa: SLF001
        {
            "change_signals": [
                {
                    "table_code": "G31",
                    "section_hint": "第 I 部分：底层资产投资情况",
                    "indicator_hint": "C.修正久期",
                    "change_type": "SCOPE_ADJUST",
                    "evidence_text": (
                        "- [新增 | 陈施霖 | 2024-12-20] "
                        "衡量单笔债券或债券投资组合估值（价格）对到期收益率变化的敏感度指标"
                    ),
                    "confidence": 0.91,
                },
                {
                    "table_code": "G31",
                    "section_hint": "第 I 部分：底层资产投资情况",
                    "indicator_hint": "C.修正久期填报定义/公式",
                    "change_type": "INSTRUCTION_ADJUST",
                    "evidence_text": (
                        "- [新增 | 陈施霖 | 2024-12-20] "
                        "MD=-(dP/P)/dy=D/(1+y/k)"
                    ),
                    "confidence": 0.95,
                },
            ]
        }
    )

    assert len(signals) == 1
    assert signals[0].indicator_hint == "C.修正久期"
    assert signals[0].change_type == "SCOPE_ADJUST"
    assert signals[0].confidence == 0.95
    assert "衡量单笔债券" in signals[0].evidence_text
    assert "MD=-(dP/P)/dy=D/(1+y/k)" in signals[0].evidence_text


def test_document_profile_enriches_scope_signal_with_current_revision_action():
    signals = [
        document_profiler.TableChangeSignal(
            table_code="G31",
            section_hint="第二部分：一般说明",
            indicator_hint="填报机构范围",
            change_type="SCOPE_ADJUST",
            evidence_text=(
                "3．填报机构：政策性银行（含开发银行）、大型商业银行（含邮储银行）、"
                "股份制商业银行、城市商业银行、直销银行、企业集团财务公司。"
            ),
            confidence=0.78,
        )
    ]
    document_text = "\n".join(
        [
            "## 当前版本修订动作（共 2 条，原始修订共 806 条）",
            "- [新增 | 陈施霖 | 2024-12-16] 直销银行、",
            "- [新增 | 周世杰 | 2021-12-09] 、金融资产投资公司",
            "",
            "## 填报说明正文",
            signals[0].evidence_text,
        ]
    )

    enriched = document_profiler._enrich_current_revision_action_evidence(  # noqa: SLF001
        signals,
        document_text,
    )

    assert "[新增 | 陈施霖 | 2024-12-16] 直销银行、" in enriched[0].evidence_text
    assert "金融资产投资公司" not in enriched[0].evidence_text
    assert "3．填报机构" in enriched[0].evidence_text


def test_document_profile_enriches_legacy_revision_tracking_block():
    signals = [
        document_profiler.TableChangeSignal(
            table_code="G31",
            section_hint="第二部分：一般说明",
            indicator_hint="填报机构范围",
            change_type="SCOPE_ADJUST",
            evidence_text=(
                "3．填报机构：政策性银行（含开发银行）、大型商业银行（含邮储银行）、"
                "股份制商业银行、城市商业银行、直销银行、企业集团财务公司、"
                "金融资产投资公司。"
            ),
            confidence=0.78,
        )
    ]
    document_text = "\n".join(
        [
            "## 修订追踪（共 806 条）",
            "- [新增 | 周世杰 | 2021-12-09] 、金融资产投资公司",
            "- [新增 | 陈施霖 | 2024-12-16] 直销银行、",
            "",
            "## 填报说明正文",
            signals[0].evidence_text,
        ]
    )

    enriched = document_profiler._enrich_current_revision_action_evidence(  # noqa: SLF001
        signals,
        document_text,
    )

    assert "[新增 | 陈施霖 | 2024-12-16] 直销银行、" in enriched[0].evidence_text
    assert "[新增 | 周世杰 | 2021-12-09] 、金融资产投资公司" not in enriched[0].evidence_text


def test_document_profile_adds_institution_scope_signal_when_model_misses(monkeypatch):
    paragraph = (
        "3．填报机构：政策性银行（含开发银行）、大型商业银行（含邮储银行）、"
        "股份制商业银行、城市商业银行、直销银行、企业集团财务公司、"
        "金融资产投资公司。"
    )
    document = RegDocument(
        filename="G31填报说明（251）.doc",
        storage_path="/tmp/G31填报说明（251）.doc",
        title="G31 指标变更扫描",
        parsed_text="\n".join(
            [
                "## 修订追踪（共 806 条）",
                "- [新增 | 周世杰 | 2021-12-09] 、金融资产投资公司",
                "- [新增 | 陈施霖 | 2024-12-16] 直销银行、",
                "",
                "## 填报说明正文",
                paragraph,
                "列项目：",
                "[C. 修正久期] ：衡量单笔债券估值对收益率变化的敏感度指标。",
            ]
        ),
        parse_quality="GOOD",
    )

    def fake_complete_json(messages):
        return (
            {
                "change_signals": [
                    {
                        "table_code": "G31",
                        "section_hint": "第 I 部分",
                        "indicator_hint": "C.修正久期",
                        "change_type": "SCOPE_ADJUST",
                        "evidence_text": "[C. 修正久期] ：衡量单笔债券估值对收益率变化的敏感度指标。",
                        "confidence": 0.9,
                    },
                    {
                        "table_code": "G31",
                        "section_hint": "第 I 部分",
                        "indicator_hint": "D列期末余额",
                        "change_type": "MODIFY",
                        "evidence_text": "是指填报机构因持有非底层资产而间接持有的期末余额。",
                        "confidence": 0.8,
                    },
                ],
                "reason": "模型仅抽出修正久期。",
            },
            '{"ok": true}',
            "fake-model",
        )

    monkeypatch.setattr(document_profiler, "complete_json", fake_complete_json)

    profile = document_profiler.generate_document_profile(
        document,
        {
            "reporting_objects": [{"object_code": "G31", "object_name": "投资业务情况表"}],
            "reporting_sections": [],
            "reporting_items": [],
        },
    )

    institution_signals = [
        signal for signal in profile.change_signals if signal.indicator_hint == "填报机构范围"
    ]

    assert len(institution_signals) == 1
    assert "[新增 | 陈施霖 | 2024-12-16] 直销银行、" in institution_signals[0].evidence_text
    assert "[新增 | 周世杰 | 2021-12-09] 、金融资产投资公司" not in institution_signals[0].evidence_text
    assert paragraph in institution_signals[0].evidence_text


def test_document_profile_adds_revision_item_definition_signals_when_model_misses(monkeypatch):
    definitions = [
        (
            "[11.1 通过互联网吸收的个人定期存款]指项目 11 中，金融机构个人客户"
            "在不通过银行网点、柜面、开卡机等实体渠道，而直接通过手机银行、网上银行、"
            "第三方互联网平台等互联网渠道为客户远程开立 II 类账户后吸收的定期存款。"
        ),
        "[11.2 通过互联网吸收的个人活期存款]指项目 11 中，金融机构吸收的活期存款。",
        "[11.a.1 通过第三方互联网平台吸收的个人定期存款]指项目 11.a 中，金融机构吸收的个人定期存款。",
        "[11.a.2 通过第三方互联网平台吸收的个人活期存款]指项目 11.a 中，金融机构吸收的个人活期存款。",
    ]
    revision_spans = [
        {"type": "TEXT", "text": "[11.1 通过", "author": "", "date": "", "action": ""},
        {"type": "INSERT", "text": "互联网", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "新增"},
        {"type": "TEXT", "text": "吸收的个人定期存款]指项目 11 中，", "author": "", "date": "", "action": ""},
        {"type": "INSERT", "text": "金融机构", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "新增"},
        {"type": "TEXT", "text": "个人客户在不通过", "author": "", "date": "", "action": ""},
        {"type": "DELETE", "text": "银行", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "删除"},
        {"type": "TEXT", "text": "网点、柜面、", "author": "", "date": "", "action": ""},
        {"type": "DELETE", "text": "开卡", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "删除"},
        {"type": "TEXT", "text": "机等实体渠道，而直接通过手机银行、网上银行、第三方互联网平台等", "author": "", "date": "", "action": ""},
        {"type": "INSERT", "text": "互联网", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "新增"},
        {"type": "TEXT", "text": "渠道为客户", "author": "", "date": "", "action": ""},
        {"type": "DELETE", "text": "远程", "author": "陈施霖", "date": "2024-12-23T08:55:00Z", "action": "删除"},
        {"type": "TEXT", "text": "开立 II 类账户后吸收的定期存款。", "author": "", "date": "", "action": ""},
    ]
    document = RegDocument(
        filename="G01填报说明（251）.doc",
        storage_path="/tmp/G01填报说明（251）.doc",
        title="G01 指标变更扫描",
        parsed_text="\n".join(
            [
                "## 当前版本修订动作（共 5 条，原始修订共 8 条）",
                "- [新增 | 陈施霖 | 2024-12-23] 金融机构",
                "- [新增 | 陈施霖 | 2024-12-23] 互联网",
                "- [删除 | 陈施霖 | 2024-12-23] 银行",
                "- [删除 | 陈施霖 | 2024-12-23] 开卡",
                "- [删除 | 陈施霖 | 2024-12-23] 远程",
                "",
                "## 当前版本原位修订片段（共 13 段）",
                *[json.dumps(span, ensure_ascii=False) for span in revision_spans],
                "",
                "## 填报说明正文",
                *definitions,
            ]
        ),
        parse_quality="GOOD",
    )

    calls = []

    def fake_complete_json(messages):
        calls.append(messages)
        if "业务变更摘要" in messages[0]["content"]:
            return (
                {
                    "business_signal_summaries": [
                        {
                            "business_signal_id": "G01::11.a.1",
                            "change_type": "SCOPE_ADJUST",
                            "changed_dimension": "统计主体",
                            "changed_from": "",
                            "changed_to": "金融机构",
                            "change_summary": "口径调整：11.a.1 统计主体明确为金融机构，影响个人定期存款填报口径。",
                            "confidence": 0.9,
                        },
                        {
                            "business_signal_id": "G01::11.a.2",
                            "change_type": "SCOPE_ADJUST",
                            "changed_dimension": "统计主体",
                            "changed_from": "",
                            "changed_to": "金融机构",
                            "change_summary": "口径调整：11.a.2 统计主体明确为金融机构，影响个人活期存款填报口径。",
                            "confidence": 0.9,
                        },
                    ]
                },
                '{"ok": true}',
                "fake-summary-model",
            )
        return (
            {
                "change_signals": [
                    {
                        "table_code": "G01",
                        "section_hint": "项目11",
                        "indicator_hint": "11.a.1通过第三方互联网平台吸收的个人定期存款",
                        "change_type": "ADD",
                        "evidence_text": "[11.a.1 通过第三方互联网平台吸收的个人定期存款]指项目 11.a 中，吸收的个人定期存款。",
                        "confidence": 0.8,
                    },
                    {
                        "table_code": "G01",
                        "section_hint": "项目11",
                        "indicator_hint": "11.a.2通过第三方互联网平台吸收的个人活期存款",
                        "change_type": "ADD",
                        "evidence_text": "[11.a.2 通过第三方互联网平台吸收的个人活期存款]指项目 11.a 中，吸收的个人活期存款。",
                        "confidence": 0.8,
                    },
                ],
                "reason": "模型只抽取了 11.a 子项。",
            },
            '{"ok": true}',
            "fake-model",
        )

    monkeypatch.setattr(document_profiler, "complete_json", fake_complete_json)

    profile = document_profiler.generate_document_profile(
        document,
        {
            "reporting_objects": [{"object_code": "G01", "object_name": "资产负债项目统计表"}],
            "reporting_sections": [],
            "reporting_items": [],
        },
    )

    signals_by_hint = {signal.indicator_hint: signal for signal in profile.change_signals}

    for definition in definitions:
        raw_hint = definition.split("]", 1)[0].lstrip("[")
        item_code, item_name = raw_hint.split(" ", 1)
        hint = f"{item_code}{item_name}"
        assert hint in signals_by_hint
        assert "[新增 | 陈施霖 | 2024-12-23] 金融机构" in signals_by_hint[hint].evidence_text
        assert definition in signals_by_hint[hint].evidence_text
        assert signals_by_hint[hint].change_type == "SCOPE_ADJUST"

    assert len(calls) == 2
    assert signals_by_hint["11.a.1通过第三方互联网平台吸收的个人定期存款"].business_signal_id == "G01::11.a.1"
    assert signals_by_hint["11.a.1通过第三方互联网平台吸收的个人定期存款"].item_codes == ["11.a.1"]
    assert signals_by_hint["11.a.1通过第三方互联网平台吸收的个人定期存款"].changed_dimension == "统计主体"
    assert signals_by_hint["11.a.1通过第三方互联网平台吸收的个人定期存款"].changed_to == "金融机构"
    assert signals_by_hint["11.a.1通过第三方互联网平台吸收的个人定期存款"].candidate_sources
    spans = signals_by_hint["11.1通过互联网吸收的个人定期存款"].revision_spans
    assert [span["type"] for span in spans if span["type"] != "TEXT"] == [
        "INSERT",
        "INSERT",
        "DELETE",
        "DELETE",
        "INSERT",
        "DELETE",
    ]
    assert [span["text"] for span in spans if span["type"] == "DELETE"] == ["银行", "开卡", "远程"]
    assert spans[1]["author"] == "陈施霖"
    assert (
        signals_by_hint["11.a.1通过第三方互联网平台吸收的个人定期存款"].change_summary
        == "口径调整：11.a.1 统计主体明确为金融机构，影响个人定期存款填报口径。"
    )


def test_document_profile_merges_candidates_before_structured_summary(monkeypatch):
    document = RegDocument(
        filename="G01填报说明（251）.doc",
        storage_path="/tmp/G01填报说明（251）.doc",
        title="G01 指标变更扫描",
        parsed_text="\n".join(
            [
                "## 当前版本修订动作（共 1 条，原始修订共 8 条）",
                "- [新增 | 陈施霖 | 2024-12-23] 金融机构",
                "",
                "## 填报说明正文",
                "[11.a.2 通过第三方互联网平台吸收的个人活期存款]指项目 11.a 中，金融机构吸收的个人活期存款。",
            ]
        ),
        parse_quality="GOOD",
    )

    def fake_complete_json(messages):
        if "业务变更摘要" in messages[0]["content"]:
            prompt = messages[1]["content"]
            assert prompt.count("business_signal_id: G01::11.a.2") == 1
            assert "candidate_sources:" in prompt
            assert "revision_actions:" in prompt
            return (
                {
                    "business_signal_summaries": [
                        {
                            "business_signal_id": "G01::11.a.2",
                            "change_type": "SCOPE_ADJUST",
                            "changed_dimension": "统计主体",
                            "changed_from": "",
                            "changed_to": "金融机构",
                            "change_summary": "口径调整：11.a.2 的统计主体明确为金融机构，影响个人活期存款填报口径。",
                            "confidence": 0.91,
                        }
                    ]
                },
                '{"ok": true}',
                "fake-summary-model",
            )
        return (
            {
                "change_signals": [
                    {
                        "table_code": "G01",
                        "section_hint": "第 IV 部分",
                        "indicator_hint": "11.a.2 通过第三方互联网平台吸收的个人活期存款（B列 其中：储蓄存款）",
                        "change_type": "ADD",
                        "evidence_text": "11.a.2 通过第三方互联网平台吸收的个人活期存款，定义中出现金融机构。",
                        "confidence": 0.3,
                    },
                    {
                        "table_code": "G01",
                        "section_hint": "第 IV 部分",
                        "indicator_hint": "11.a.1/11.a.2 附注解释",
                        "change_type": "SCOPE_ADJUST",
                        "evidence_text": "11.a.1/11.a.2 附注解释的定义发生调整。",
                        "confidence": 0.3,
                    },
                ],
                "reason": "模型输出重复候选。",
            },
            '{"ok": true}',
            "fake-model",
        )

    monkeypatch.setattr(document_profiler, "complete_json", fake_complete_json)

    profile = document_profiler.generate_document_profile(
        document,
        {
            "reporting_objects": [{"object_code": "G01", "object_name": "资产负债项目统计表"}],
            "reporting_sections": [],
            "reporting_items": [],
        },
    )

    signals_by_id = {signal.business_signal_id: signal for signal in profile.change_signals}

    assert list(signals_by_id) == ["G01::11.a.1", "G01::11.a.2"]
    signal = signals_by_id["G01::11.a.2"]
    assert signal.item_codes == ["11.a.2"]
    assert signal.changed_dimension == "统计主体"
    assert signal.changed_to == "金融机构"
    assert signal.change_summary == "口径调整：11.a.2 的统计主体明确为金融机构，影响个人活期存款填报口径。"
    assert len(signal.candidate_sources) == 3


def test_merge_business_signals_sorts_item_codes_and_text_labels_together():
    signals = [
        document_profiler.TableChangeSignal(
            table_code="G01",
            indicator_hint="填报机构范围",
            change_type="SCOPE_ADJUST",
            evidence_text="填报机构范围调整。",
        ),
        document_profiler.TableChangeSignal(
            table_code="G01",
            indicator_hint="11.a.1通过第三方互联网平台吸收的个人定期存款",
            change_type="SCOPE_ADJUST",
            evidence_text="11.a.1 统计口径调整。",
        ),
    ]

    merged = document_profiler._merge_business_signals(signals)  # noqa: SLF001

    assert [signal.business_signal_id for signal in merged] == [
        "G01::11.a.1",
        "G01::填报机构范围",
    ]


def test_fallback_change_summary_keeps_generic_wording_without_term_mapping():
    institution_signal = document_profiler.TableChangeSignal(
        table_code="G31",
        section_hint="第二部分：一般说明",
        indicator_hint="填报机构范围",
        change_type="SCOPE_ADJUST",
        evidence_text="[新增 | 陈施霖 | 2024-12-16] 直销银行、；3．填报机构：第IV部分：政策性银行、直销银行。",
        confidence=0.86,
    )
    column_signal = document_profiler.TableChangeSignal(
        table_code="G31",
        section_hint="第 I 部分：底层资产投资情况",
        indicator_hint="D列/ E列列位说明（因新增C列发生顺延）",
        change_type="SCOPE_ADJUST",
        evidence_text="[新增 | 陈施霖 | 2024-12-16] C.；D列/E列列位说明因新增C列发生顺延。",
        confidence=0.72,
    )

    institution_summary = document_profiler._fallback_change_summary(institution_signal)  # noqa: SLF001
    column_summary = document_profiler._fallback_change_summary(column_signal)  # noqa: SLF001

    assert "修订记录新增" in institution_summary
    assert "修订记录新增" in column_summary
    assert "限定" not in institution_summary
    assert "限定" not in column_summary
    assert "统计主体明确为金融机构" not in institution_summary


def test_document_profile_route_uses_in_scope_actionable_signal():
    signals = [
        document_profiler.TableChangeSignal(
            table_code="G24",
            indicator_hint="同业融入余额",
            change_type="SCOPE_ADJUST",
            evidence_text="调整G24同业融入余额统计口径。",
            confidence=0.9,
        )
    ]

    route = document_profiler._derive_route(["G24"], [], signals)  # noqa: SLF001
    confidence = document_profiler._compute_confidence(signals, ["G24"])  # noqa: SLF001

    assert route == "FULL_ANALYSIS"
    assert confidence == 0.9


def test_document_profile_route_light_archives_out_of_scope_tables():
    signals = [
        document_profiler.TableChangeSignal(
            table_code="G11",
            change_type="SCOPE_ADJUST",
            evidence_text="调整G11相关口径。",
            confidence=0.8,
        )
    ]

    route = document_profiler._derive_route([], ["G11"], signals)  # noqa: SLF001

    assert route == "LIGHTWEIGHT_ARCHIVE"
