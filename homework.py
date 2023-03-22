import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    StatusCodeError,
    RequestError,
    HomeworkStatusError,
    TelegramSendMessageError
)

load_dotenv()
logger = logging.getLogger(__name__)

EMPTY_TOKEN = (
    'Отсутствует один из обязательных токенов. '
    'Необходимо проверить наличие для продолжения работы.'
)
REQUEST_ERROR = (
    'Запросе к URL {url} с параметрами {params} '
    'вернул ошибку {error}'
)
INCORRECT_STATUS = 'Запрос вернул некорректный статус {status}.'
SUCCESSFUL_MESSAGE = 'Сообщение успешно отправлено.'
TYPE_ERROR = (
    'Некорректный тип данных. Ожидался {expected_type}. '
    'Был получен {received_type}.'
)
KEY_ERROR = (
    'Отсутствует ключ необходимый ключ в словаре {dictionary}. '
    'Доступные ключи {received_keys}.'
)
HOMEWORK_STATUS_ERROR = (
    'Получен неизвестный статус {status} домашней работы. '
    'Необходимо дополнить значения словаря {dictionary}'
)
SEND_MESSAGE_ERROR = (
    'Не удалось отправить сообщение {message} в чат {chat_id}.'
)
LAST_ERROR = 'Сообщение об ошибке было отправлено.'


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


def check_tokens() -> bool:
    """Проверяет наличие токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение автору работы."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.TelegramError as error:
        logger.error(error)
        raise TelegramSendMessageError(
            SEND_MESSAGE_ERROR.format(
                message=message, chat_id=TELEGRAM_CHAT_ID
            )
        )
    else:
        logger.debug(SUCCESSFUL_MESSAGE)


def get_api_answer(timestamp: int) -> dict:
    """Возвращает результат ревью."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            params=payload,
            headers=HEADERS
        )
    except requests.RequestException as request_error:
        raise RequestError(
            REQUEST_ERROR.format(
                url=ENDPOINT, params=payload, error=request_error
            )
        )
    if response.status_code != HTTPStatus.OK:
        raise StatusCodeError(
            INCORRECT_STATUS.format(status=response.status_code)
        )
    return response.json()


def check_response(response: dict) -> list:
    """Валидирует ответ от сервиса."""
    if not isinstance(response, dict):
        raise TypeError(
            TYPE_ERROR.format(
                expected_type=dict, received_type=type(response)
            )
        )
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError(
            KEY_ERROR.format(
                dictionary='response', received_keys=response.keys()
            )
        )
    if not isinstance(homeworks, list):
        raise TypeError(
            TYPE_ERROR.format(
                expected_type=list, received_type=type(homeworks)
            )
        )
    return homeworks


def parse_status(homework: dict) -> str:
    """Возвращает сообщение с результатом ревью."""
    status = homework.get('status')
    homework_name = homework.get('homework_name')
    if status is None or homework_name is None:
        raise KeyError(
            KEY_ERROR.format(
                dictionary='homework', received_keys=homework.keys()
            )
        )
    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusError(
            HOMEWORK_STATUS_ERROR.format(
                status=status, received_keys=HOMEWORK_VERDICTS
            )
        )
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(EMPTY_TOKEN)
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                message = parse_status(homework)
                send_message(bot, message)
                timestamp = response.get('current_date')
        except TelegramSendMessageError as tg_error:
            logger.error(repr(tg_error))
        except Exception as error:
            message = f'Сбой в работе программы: {repr(error)}'
            if message == last_error_message:
                logger.info(LAST_ERROR)
                continue
            last_error_message = message
            try:
                send_message(bot, message)
            except TelegramSendMessageError as tg_error:
                logger.error(repr(tg_error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s: %(levelname)s: %(message)s: %(name)s',
        handlers=[
            logging.FileHandler("main.log", mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()
