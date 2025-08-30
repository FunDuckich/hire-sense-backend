from app.services import tts_service


def test_synthesis():
    print("--- Тест: Синтез речи ---")

    test_text = "Привет, это тестовая фраза для проверки синтеза речи."

    try:
        audio_data = tts_service.synthesize_speech(test_text)

        assert audio_data is not None
        assert isinstance(audio_data, bytes)
        assert len(audio_data) > 1000
        with open("test_output.ogg", "wb") as f:
            f.write(audio_data)

        print("✅ Синтез речи успешно завершен!")
        print("   Результат сохранен в файл 'test_output.ogg'. Можешь его прослушать.")

    except Exception as e:
        print(f"❌ Ошибка во время синтеза речи: {e}")


if __name__ == "__main__":
    test_synthesis()