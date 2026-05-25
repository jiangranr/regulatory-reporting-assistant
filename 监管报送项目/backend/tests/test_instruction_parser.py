from app.services.instruction_parser import _parse_html


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
