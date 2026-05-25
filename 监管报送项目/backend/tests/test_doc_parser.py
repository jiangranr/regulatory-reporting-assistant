from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.doc_parser import extract_doc_text, generate_change_summary

G31_DOC = Path("/Users/jiangqiuping/webproject/监管报送项目/一表通/附件4：报表表样和填报说明汇总/2.修订报表（基础类、业务类、支持发展类）/G31/G31填报说明（251）.doc")


@pytest.mark.skipif(not G31_DOC.exists(), reason="G31 doc not available")
def test_extract_doc_text_returns_nonempty():
    text = extract_doc_text(G31_DOC)
    assert isinstance(text, str)
    assert len(text) > 100


def test_extract_doc_text_missing_file():
    text = extract_doc_text(Path("/nonexistent/file.doc"))
    assert text == ""


@pytest.mark.asyncio
async def test_generate_change_summary_mocked():
    fake_summary = "本次修订：新增穿透后列，调整期末余额口径。"
    with patch("app.services.doc_parser.complete_json") as mock_complete_json:
        mock_complete_json.return_value = ({"summary": fake_summary}, "raw", "model")
        summary = await generate_change_summary("some long doc text", object_code="G31")
    assert summary == fake_summary


@pytest.mark.asyncio
async def test_generate_change_summary_llm_fail_returns_empty():
    with patch("app.services.doc_parser.complete_json") as mock_complete_json:
        mock_complete_json.side_effect = Exception("LLM timeout")
        summary = await generate_change_summary("some text", object_code="G31")
    assert summary == ""
