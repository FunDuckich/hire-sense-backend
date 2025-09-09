import easyocr
from .base import OcrServiceBase


class EasyOcrService(OcrServiceBase):
    def __init__(self):
        print("Инициализация EasyOCR Reader (может занять время)...")
        self.reader = easyocr.Reader(['ru', 'en'], gpu=False)  # TODO gpu=False для CPU-вычислений
        print("EasyOCR Reader инициализирован.")

    def recognize(self, image_bytes_list: list[bytes]) -> str:
        full_text_parts = []
        print(f"EasyOCR: Получено {len(image_bytes_list)} изображений для распознавания.")

        for i, img_bytes in enumerate(image_bytes_list):
            try:
                result = self.reader.readtext(img_bytes)
                page_text = " ".join([text for _, text, _ in result])
                full_text_parts.append(page_text)
                print(f"  - Изображение #{i + 1} распознано, длина текста: {len(page_text)}")
            except Exception as e:
                print(f"  - Ошибка при распознавании изображения #{i + 1}: {e}")

        return "\n".join(full_text_parts)