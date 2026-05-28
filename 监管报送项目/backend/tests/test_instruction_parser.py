from app.services.instruction_parser import (
    InstructionParseResult,
    RevisionFragment,
    _parse_html,
    build_pair_document_text,
    current_version_revisions,
    extract_regulatory_metadata,
)


def test_parse_html_extracts_non_black_highlights():
    html = """
    <html><body>
      <p style="color: #000000">普通说明</p>
      <p style="color: red">新增附表G31-A同业交易对手大额风险暴露明细表</p>
      <font color="#0070C0">填写交易对手名称和风险暴露余额</font>
    </body></html>
    """

    result = _parse_html(html)

    assert "普通说明" in result.text
    assert [item.text for item in result.highlights] == [
        "新增附表G31-A同业交易对手大额风险暴露明细表",
        "填写交易对手名称和风险暴露余额",
    ]


def test_current_version_revisions_keeps_latest_year_only():
    revisions = [
        RevisionFragment("INSERT", "old", "2021-12-09T10:00:00Z", "、金融资产投资公司"),
        RevisionFragment("INSERT", "new", "2024-12-16T10:00:00Z", "直销银行、"),
        RevisionFragment("DELETE", "new", "2024-12-20T10:00:00Z", "旧列号D"),
    ]

    filtered = current_version_revisions(revisions)

    assert [r.text for r in filtered] == ["直销银行、", "旧列号D"]


def test_pair_document_text_keeps_current_revision_action_metadata():
    instruction = InstructionParseResult(
        text="填报说明正文",
        html="",
        highlights=[],
        comments=[],
        revisions=[
            RevisionFragment("INSERT", "old", "2021-12-09T10:00:00Z", "、金融资产投资公司"),
            RevisionFragment("INSERT", "new", "2024-12-16T10:00:00Z", "直销银行、"),
            RevisionFragment("DELETE", "new", "2024-12-20T10:00:00Z", "旧列号D"),
        ],
        parser="doc_html",
    )

    text = build_pair_document_text("G31(251).xls", "G31填报说明（251）.doc", instruction)

    assert "当前版本修订动作（共 2 条，原始修订共 3 条）" in text
    assert "[新增 | new | 2024-12-16] 直销银行、" in text
    assert "[删除 | new | 2024-12-20] 旧列号D" in text
    assert "、金融资产投资公司" not in text


# ---------------------------------------------------------------------------
# extract_regulatory_metadata
# ---------------------------------------------------------------------------

_SAMPLE_THREE_AGENCIES = """国家金融监督管理总局  中国人民银行  国家外汇管理局

公 告

〔2026〕第 15 号


关于规范同业资金往来与投资业务跨表填报口径的公告


为深化《银行业金融机构非现场监管报表》（以下简称 1104 报表）数据治理工作，提升 G24 与 G31 之间的口径一致性，确保穿透式监管要求落地，现就相关填报口径调整事项公告如下，自 2026 年 7 月 1 日起施行。


一、关于 G24 表填报范围的调整……

四、过渡期安排
2026 年第三季度报表（数据日期 2026-09-30）按本公告口径首次报送。


                                  国家金融监督管理总局
                                  中国人民银行
                                  国家外汇管理局
                                  2026 年 5 月 26 日
"""


def test_extract_regulatory_metadata_full_hit():
    meta = extract_regulatory_metadata(_SAMPLE_THREE_AGENCIES)

    assert meta.document_no == "〔2026〕第 15 号"
    assert "国家金融监督管理总局" in meta.issuing_authority
    assert "中国人民银行" in meta.issuing_authority
    assert "国家外汇管理局" in meta.issuing_authority
    assert meta.published_at == "2026-05-26"
    assert meta.effective_date == "2026-07-01"
    assert meta.first_report_period == "2026Q3"
    assert meta.regulatory_intent.startswith("为深化")
    assert "确保穿透式监管要求落地" in meta.regulatory_intent
    assert meta.status == "OK"


def test_extract_regulatory_metadata_empty_text():
    meta = extract_regulatory_metadata("")
    assert meta.status == "FAILED"
    assert meta.document_no == ""
    assert meta.effective_date == ""


def test_extract_regulatory_metadata_partial():
    """缺生效日 + 报送时点，只有发文单位和发布日期。"""
    text = """中国人民银行

关于优化数据治理工作的通知


    2026 年 3 月 10 日
"""
    meta = extract_regulatory_metadata(text)
    assert meta.issuing_authority == "中国人民银行"
    assert meta.published_at == "2026-03-10"
    assert meta.effective_date == ""
    assert meta.first_report_period == ""
    assert meta.status == "PARTIAL"


def test_extract_regulatory_metadata_doc_no_with_prefix():
    """带机构前缀的文号 银保监办发〔2026〕14 号。"""
    text = "银保监办发〔2026〕14 号 关于 G24 表统计口径调整的通知"
    meta = extract_regulatory_metadata(text)
    assert meta.document_no == "银保监办发〔2026〕14 号"


def test_extract_regulatory_metadata_monthly_report_period():
    text = "本通知自 2026 年 1 月 1 日起施行，自 2026 年 2 月起报送日按新口径填报。"
    meta = extract_regulatory_metadata(text)
    assert meta.effective_date == "2026-01-01"
    assert meta.first_report_period == "2026-02"
