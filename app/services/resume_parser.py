import io
from docx import Document
import fitz
from fastapi import UploadFile, HTTPException, status


async def parse_resume(file: UploadFile) -> str:
    content_type = file.content_type
    file_content = await file.read()

    if content_type == "application/pdf":
        try:
            pdf_document = fitz.open(stream=file_content, filetype="pdf")
            text = ""
            for page in pdf_document:
                text += page.get_text()
            pdf_document.close()
            return text
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error parsing PDF file: {e}"
            )

    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            doc = Document(io.BytesIO(file_content))
            text = "\n".join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error parsing DOCX file: {e}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Please upload a PDF or DOCX file."
        )
