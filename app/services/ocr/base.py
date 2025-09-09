
from abc import ABC, abstractmethod

class OcrServiceBase(ABC):

    @abstractmethod
    def recognize(self, image_bytes_list: list[bytes]) -> str:
        raise NotImplementedError