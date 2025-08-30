def test_interview_response_generation():
    print("\n--- Тест: Генерация вопроса для интервью ---")

    # --- Подготовим фейковый контекст ---
    mock_vacancy = {
        "job_title": "Python-разработчик",
        "evaluation_criteria": [
            {"criterion": "Опыт с FastAPI", "weight": 50},
            {"criterion": "Знание SQL", "weight": 50}
        ]
    }

    mock_resume = {
        "summary": "Кандидат выглядит подходящим, но нужно уточнить опыт с асинхронностью.",
        "questions_to_ask": ["Расскажите подробнее о вашем опыте с FastAPI."]
    }

    mock_history = [
        {"role": "system", "text": "..."},
        {"role": "assistant", "text": "Здравствуйте! Расскажите немного о себе."},
        {"role": "user", "text": "Добрый день, я занимаюсь бэкенд-разработкой уже 5 лет."}
    ]

    try:
        next_question = llm_service.get_interview_response(mock_history, mock_vacancy, mock_resume)
        assert next_question is not None
        assert isinstance(next_question, str)

        print("✅ Генерация вопроса успешно завершена!")
        print(f"   Сгенерированный вопрос: '{next_question}'")

    except Exception as e:
        print(f"❌ Ошибка во время генерации вопроса: {e}")


if __name__ == "__main__":
    test_interview_response_generation()