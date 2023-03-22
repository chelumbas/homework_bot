class StatusCodeError(Exception):
    """Невалидный код ответа"""
    pass


class RequestError(Exception):
    """Ошибка запроса к сервису."""
    pass


class HomeworkStatusError(Exception):
    """Новый статус домашней работы."""
    pass


class TelegramSendMessageError(Exception):
    """Ошибка отправки сообщения в Telegram."""
    pass
