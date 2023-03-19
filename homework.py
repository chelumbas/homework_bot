import telegram
import time
import requests
import sys
import os
import logging
from dataclasses import dataclass
from typing import Optional
from http import HTTPStatus
from exceptions import StatusCodeError
from dotenv import load_dotenv
load_dotenv()


@dataclass(frozen=True)
class LoggedMessages:
    """Текст сообщения ошибок."""

    empty_token = (
        'Отсутствует один из обязательных токенов. '
        'Необходимо проверить наличие для продолжения работы.'
    )
    incorrect_status = 'Запрос вернул некорректный статус.'
    former_status = 'Статус работы не изменился.'
    successful_message = 'Сообщение успешно отправлено.'
    type_error = 'Получены данные в некорректного формата:'
    key_error = 'Получена переменная со следующими ключами:'


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s: %(levelname)s: %(message)s: %(name)s',
    handlers=[
        logging.FileHandler("main.log", mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)


def check_tokens() -> bool:
    """Проверяет наличие токенов."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN:
        logging.critical(LoggedMessages.empty_token)
        return False
    return True


def send_message(bot, message):
    """Отправляет сообщение автору работы."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.TelegramError as error:
        logging.error(error)
    logging.debug(LoggedMessages.successful_message)


def get_api_answer(timestamp: int) -> Optional[dict]:
    """Возвращает результат ревью."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            params=payload,
            headers=HEADERS
        )
    except requests.RequestException as request_error:
        logging.warning(request_error)
        return None
    if response.status_code != HTTPStatus.OK:
        raise StatusCodeError(
            LoggedMessages.incorrect_status,
            ENDPOINT,
            response.status_code,
            response.text
        )
    return response.json()


def check_response(response: dict) -> dict:
    """Валидирует ответ от сервиса."""
    if not isinstance(response, dict):
        raise TypeError(LoggedMessages.type_error, type(response))
    homeworks = response.get('homeworks')
    if not homeworks:
        raise KeyError((LoggedMessages.key_error, response.keys()))
    if not isinstance(homeworks, list):
        raise TypeError(LoggedMessages.type_error, type(homeworks))
    homework = homeworks[0]
    if not homework:
        raise ValueError
    return homework


def parse_status(homework: dict) -> str:
    """Возвращает сообщение с результатом ревью."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if (
            not status or status not in HOMEWORK_VERDICTS.keys()
            or not homework_name
    ):
        raise KeyError(LoggedMessages.key_error, homework.keys())
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    last_homework_status = ''
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            status = parse_status(homework)
            if status != last_homework_status:
                last_homework_status = status
                send_message(bot, status)
            else:
                logging.debug(LoggedMessages.former_status)
        except Exception as error:
            message = f'Сбой в работе программы: {repr(error)}'
            if message != last_error_message:
                last_error_message = message
                send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
