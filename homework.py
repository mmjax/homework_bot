import logging
import os
import time
from logging import StreamHandler, FileHandler

from dotenv import load_dotenv
import requests
import telegram
from telegram.ext import CommandHandler, Updater

from exceptions import UnexpectedCodeError, ResponseError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

GREATING = (
    'Привет, {}. Я помогу тебе узнать, '
    'на каком этапе проверки твоя домашка :)'
)
UNKNOWN_STATUS = 'Неизвестный статус. Ошибка {}'
CHANGED_STATUS = 'Изменился статус проверки работы "{}". {}'
RESPONSE_NOT_DICT = 'Ответ на запрос не является словарём'
HOMEWORKS_NOT_IN_RESPONSE = 'В ответе на запрос нет ключа homeworks'
HOMEWORKS_NOT_LIST = 'homeworks не является списком'
API_ANSWER_ERROR = ('Не удалось получить ответ от API. '
                    'Ошибка - {} Endpoint - {} Header - {} params - {}')
SUCCESSFUL_SENDING = 'Сообщение {} успешно отправлено!'
SENDING_ERROR = 'Не удалось отправить сообщение {}. Ошибка {}'
API_ERROR = ('ключ ошибки - {} response error - {} '
             'Endpoint - {} Heders - {} params - {}')
ENDPOINT_ERROR = ('Недоступен эндпоинт {}. Код ответа {}.'
                  ' Params - {}. Header - {}')
ERROR = 'Сбой в работе программы: {}'
TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
MISSING_TOKEN = 'Отсутствует токен {}'

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в чат телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(SUCCESSFUL_SENDING.format(message))
    except Exception as error:
        logging.exception(SENDING_ERROR.format(message, error))


def wake_up(update, context):
    """Приветствующее слово."""
    chat = update.effective_chat
    name = update.message.chat.first_name
    context.bot.send_message(
        chat_id=chat.id,
        text=GREATING.format(name),
    )


def get_api_answer(current_timestamp):
    """Получение списка из API."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions as error:
        raise ConnectionError(
            API_ANSWER_ERROR.format(error, ENDPOINT, HEADERS, params)
        )
    response_json = response.json()
    status_code = response.status_code
    for key in ['code', 'error']:
        if key in response_json:
            raise ResponseError(
                API_ERROR.format(
                    key,
                    response_json[key],
                    ENDPOINT,
                    HEADERS,
                    params
                )
            )
    if status_code != 200:
        raise UnexpectedCodeError(
            ENDPOINT_ERROR.format(ENDPOINT, status_code, params, HEADERS)
        )
    logging.debug('Endpoint = 200')
    return response_json


def check_response(response):
    """Проверка ключей о response."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_NOT_DICT)
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_NOT_IN_RESPONSE)
    if not isinstance(response['homeworks'], list):
        raise TypeError(HOMEWORKS_NOT_LIST)
    return response['homeworks']


def parse_status(homework):
    """Извлечение информации о домашней работе и статуса этой работы."""
    status = homework['status']
    verdict = VERDICTS[status]
    if status not in VERDICTS:
        raise ValueError(UNKNOWN_STATUS.format(status))
    return CHANGED_STATUS.format(homework['homework_name'], verdict)


def check_tokens():
    """Проверка токенов."""
    invalid_tokens = [name for name in TOKENS if not globals()[name]]
    if invalid_tokens:
        for name in invalid_tokens:
            logging.error(MISSING_TOKEN.format(name))
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError('WRONG_TOKENS')
    updater = Updater(TELEGRAM_TOKEN)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework_list = check_response(response)
            if homework_list:
                send_message(bot, parse_status(homework_list[0]))
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = ERROR.format(error)
            logging.error(message)
            send_message(bot, message)
        updater.dispatcher.add_handler(CommandHandler('start', wake_up))
        updater.start_polling()
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            StreamHandler(),
            FileHandler(filename=__file__ + '.log', encoding='UTF-8')
        ],
        format=(
            '%(asctime)s - %(levelname)s - %(funcName)s '
            '- %(lineno)d - %(message)s'
        ),
    )
    main()
