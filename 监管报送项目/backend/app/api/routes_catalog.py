"""报表目录维护接口：zip 上传、批次查询。"""
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlmodel import Session, select

from app.core.database import get_session
from app.models.db_models import RegCatalogBatch, RegCatalogBatchItem
from app.services.catalog_ingestor import create_batch, process_catalog_zip

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.post("/upload-zip", status_code=status.HTTP_201_CREATED)
async def upload_catalog_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source_document_ref: str = Form(default=""),
    object_codes: str = Form(default=""),
    session: Session = Depends(get_session),
) -> dict:
    # 1. 验证 zip 文件
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式文件")

    content = await file.read()
    if len(content) < 4 or content[:4] != b"PK\x03\x04":
        raise HTTPException(status_code=400, detail="文件不是有效的 zip 格式")

    # 解析 object_codes 白名单（逗号分隔，去空格，转大写）
    codes_filter: list[str] = [c.strip().upper() for c in object_codes.split(",") if c.strip()]

    # 2. 保存 zip 到临时目录（BackgroundTask 异步处理，不能用 with 上下文）
    tmp_dir = Path(tempfile.mkdtemp(prefix="catalog_batch_"))
    zip_path = tmp_dir / (file.filename or "upload.zip")
    zip_path.write_bytes(content)
    extract_to = tmp_dir / "extracted"

    # 3. 创建 batch 记录（PENDING 状态）
    batch = create_batch(session, zip_filename=file.filename or "", source_doc_ref=source_document_ref)

    # 4. 快速扫描以提前获知 version_label 和 total_count（应用白名单过滤）
    from app.services.zip_scanner import scan_zip as _quick_scan
    try:
        version_label, file_sets = _quick_scan(zip_path, extract_to)
        if codes_filter:
            file_sets = [fs for fs in file_sets if fs.object_code.upper() in codes_filter]
        batch.version_label = version_label
        batch.total_count = len(file_sets)
        batch.status = "PROCESSING"
        session.add(batch)
        session.commit()
        session.refresh(batch)
    except Exception:
        pass  # 扫描失败时不阻断，后台任务会处理

    # 5. 添加后台任务（传入白名单，后台任务再次过滤）
    background_tasks.add_task(process_catalog_zip, batch.id, zip_path, extract_to, codes_filter or None)

    return {
        "batch_id": batch.id,
        "batch_code": batch.batch_code,
        "version_label": batch.version_label,
        "total_count": batch.total_count,
        "status": batch.status,
    }


@router.get("/batches")
def list_batches(session: Session = Depends(get_session)) -> list[dict]:
    batches = session.exec(
        select(RegCatalogBatch).order_by(RegCatalogBatch.created_at.desc())  # type: ignore[arg-type]
    ).all()
    return [
        {
            "id": b.id,
            "batch_code": b.batch_code,
            "version_label": b.version_label,
            "source_zip_filename": b.source_zip_filename,
            "total_count": b.total_count,
            "done_count": b.done_count,
            "fail_count": b.fail_count,
            "status": b.status,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ]


@router.get("/batches/{batch_id}")
def get_batch_detail(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = session.get(RegCatalogBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = session.exec(
        select(RegCatalogBatchItem).where(RegCatalogBatchItem.batch_id == batch_id)
    ).all()

    return {
        "id": batch.id,
        "batch_code": batch.batch_code,
        "version_label": batch.version_label,
        "source_zip_filename": batch.source_zip_filename,
        "source_document_ref": batch.source_document_ref,
        "total_count": batch.total_count,
        "done_count": batch.done_count,
        "fail_count": batch.fail_count,
        "status": batch.status,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "finished_at": batch.finished_at.isoformat() if batch.finished_at else None,
        "items": [
            {
                "id": item.id,
                "object_code": item.object_code,
                "change_type": item.change_type,
                "table_category": item.table_category,
                "parse_status": item.parse_status,
                "parse_error": item.parse_error,
                "change_summary": item.change_summary,
                "items_count": item.items_count,
            }
            for item in items
        ],
    }
