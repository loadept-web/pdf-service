from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from ..services.file_service import FileService
from io import BytesIO
from typing import Literal, List

router = APIRouter(prefix="/pdf", tags=["PDF Operations"])
file_service = FileService()

accepted_quality = {
    "extreme": "screen",
    "normal": "ebook",
    "low": "printer"
}

@router.post("/compress", summary="Compress PDF", description="Compress a PDF file with specified quality level")
async def pdf_compressor(
    file: UploadFile = File(..., description="PDF file to compress"),
    quality: Literal["extreme", "normal", "low"] = Form(..., description="Compression level: extreme (max compression), normal (balanced), low (min compression)")
):
    try:
        if file.content_type != "application/pdf":
            raise HTTPException(400, "File type is incorrect")

        pdf_bytes = await file.read()
        compressed_file: bytes
        actual_size = file.size

        compressed_file = file_service.compress_pdf_tmp(pdf_bytes, accepted_quality[quality])

        if not compressed_file:
            raise HTTPException(500, "Compression did not generate any results")    

        file_name = file.filename.removesuffix('.pdf')
        compressed_size = len(compressed_file)
        reduction = ((actual_size - compressed_size) / actual_size) * 100

        return StreamingResponse(
            BytesIO(compressed_file),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}_compress.pdf"',
                "Content-Length": str(len(compressed_file)),
                "X-Original-Size": str(actual_size),
                "X-Compressed-size": str(compressed_size),
                "X-Reduction-Percent": f"{reduction:.2f}",
                "X-Quality-Level": quality
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/merge", summary="Merge PDFs", description="Merge multiple PDF files into one")
async def pdf_merge(
    files: List[UploadFile] = File(..., description="List of PDF files to merge (minimum 2)"),
):
    try:
        if len(files) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 PDF files are required for merging."
            )

        for file in files:
            if file.content_type != "application/pdf":
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid file type: {file.filename} must be a PDF."
                )

        bytes_list = [await f.read() for f in files]

        merged_file = file_service.merge_pdf(bytes_list)

        if not merged_file:
            raise HTTPException(500, "Merge did not generate any results")    

        return StreamingResponse(
            BytesIO(merged_file),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="merged.pdf"',
                "Content-Length": str(len(merged_file)),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
