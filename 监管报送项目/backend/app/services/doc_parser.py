"""Doc 填报说明解析器：提取文本 + LLM 变更摘要。支持 .docx 和旧版 .doc。"""
import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.services.llm_client import LLMClientError, complete_json


def extract_doc_text(file_path: Path) -> str:
    """
    从 .doc 或 .docx 文件提取纯文本。

    - .docx：使用 python-docx
    - .doc：使用 soffice (LibreOffice) 转换为 txt
    - 文件不存在或转换失败：返回空字符串
    """
    if not file_path.exists():
        return ""

    suffix = file_path.suffix.lower()
    if suffix == ".docx":
        return _extract_docx(file_path)
    elif suffix == ".doc":
        return _extract_doc_via_soffice(file_path)
    return ""


def _extract_docx(file_path: Path) -> str:
    try:
        from docx import Document

        doc = Document(str(file_path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ""


def _extract_doc_via_soffice(file_path: Path) -> str:
    """使用 LibreOffice headless 将 .doc 转为 txt。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return ""

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to",
                    "txt:Text",
                    "--outdir",
                    tmp_dir,
                    str(file_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            txt_file = Path(tmp_dir) / (file_path.stem + ".txt")
            if txt_file.exists():
                return txt_file.read_text(encoding="utf-8", errors="ignore")
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


async def generate_change_summary(full_text: str, object_code: str) -> str:
    """
    调用 LLM，从填报说明全文中提取本次版本的变更要点。
    LLM 调用失败时静默返回空字符串，不阻塞入库流程。

    使用 complete_json（同步函数），在线程池中执行以避免阻塞事件循环。
    """
    if not full_text.strip():
        return ""

    prompt = f"""以下是监管报表 {object_code} 的填报说明全文。
请提取本次版本修订的变更要点，以简洁的要点列表形式输出（不超过 200 字）。
如果文中没有明确的变更说明，输出"无明确变更说明"。
请用 JSON 格式返回，格式为：{{"summary": "变更要点内容"}}

填报说明：
{full_text[:3000]}
"""
    messages = [{"role": "user", "content": prompt}]

    try:
        result_dict, _raw, _model = await asyncio.to_thread(complete_json, messages)
        return result_dict.get("summary", "")
    except Exception:
        return ""
