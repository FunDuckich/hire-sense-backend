import io
from docx import Document
import fitz
from fastapi import UploadFile, HTTPException, status
from .ocr import ocr_service


async def parse_file(file: UploadFile) -> str:
    content_type = file.content_type
    file_content_bytes = await file.read()

    if content_type == "application/pdf":
        text = ""
        try:
            pdf_document = fitz.open(stream=file_content_bytes, filetype="pdf")
            for page in pdf_document:
                text += page.get_text()
            pdf_document.close()

            if not text.strip():
                print("Текстовый слой в PDF не найден или пуст. Включаем OCR-фолбэк...")

                pdf_document_for_ocr = fitz.open(stream=file_content_bytes, filetype="pdf")
                image_bytes_list = []
                for page in pdf_document_for_ocr:
                    pix = page.get_pixmap(dpi=300)
                    image_bytes_list.append(pix.tobytes("png"))
                pdf_document_for_ocr.close()

                text = ocr_service.recognize(image_bytes_list)

            return text

        except Exception as e:
            print(f"Ошибка при обработке PDF: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error parsing PDF file: {e}"
            )

    elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        try:
            doc = Document(io.BytesIO(file_content_bytes))
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