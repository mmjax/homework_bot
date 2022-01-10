import logging
import os
import requests
import time
import telegram

from telegram.ext import CommandHandler, Updater

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='messages.log',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s',
    filemode='a'
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в чат телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info('Сообщение успешно отправлено!')
    except Exception as error:
        logging.error(f'Не удалось отправить сообщение. Ошибка {error}')


def wake_up(update, context):
    """Приветствующее слово."""
    chat = update.effective_chat
    name = update.message.chat.first_name
    context.bot.send_message(
        chat_id=chat.id,
        text=(
            'Привет, {}. Я тебе помогу узнать,'
            'на каком этапе проверки твоя домашка :)').format(name),
    )


def get_api_answer(current_timestamp):
    """Получение списка из API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        raise logging.error(
            f'Не удалось получить ответ от API. Ошибка {error}'
        )
    response_json = response.json()
    status_code = response.status_code
    if status_code != 200:
        if 'error' in response_json:
            response_error = response_json['error']
            logging.error(
                f'response error - {response_error},'
                f'status code - {status_code}'
            )
        if 'code' in response_json:
            response_error = response_json['code']
            logging.error(
                f'response error - {response_error},'
                f'status code - {status_code}'
            )
        else:
            logging.error(
                f'Недоступен эндпоинт {ENDPOINT}.'
                f'Код ответа {status_code}'
            )
        raise
    logging.debug('Endpoint = 200')
    return response_json


def check_response(response):
    """Проверка ключей о response."""
    if not isinstance(response, dict):
        raise TypeError('RESPONSE_NOT_DICT')
    if 'homeworks' not in response:
        raise KeyError('HOMEWORKS_NOT_IN_RESPONSE')
    if not isinstance(response['homeworks'], list):
        raise TypeError('HOMEWORKS_NOT_LIST')
    return response['homeworks']


def parse_status(homework):
    """Извлечение информации о домашней работе и статуса этой работы."""
    homework_status = homework['status']
    if 'homework_name' not in homework:
        logging.error('Нет ключа')
        raise KeyError('HOMEWORK_NAME_NOT_FOUND')
    homework_name = homework['homework_name']
    if homework_status not in HOMEWORK_STATUSES.keys():
        raise KeyError('UNKNOWN_STATUS')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка токенов."""
    tokens = {
        'Токен яндекс практикума': PRACTICUM_TOKEN,
        'Токен телеграм бота': TELEGRAM_TOKEN,
        'Id телеграм чата': TELEGRAM_CHAT_ID
    }
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
        logging.info('Все токены в норме')
        return True
    else:
        for name, token in tokens.items():
            if token is None:
                logging.critical(f'Ошбка в токене {name}')
        return False


def main():
    """Основная логика работы бота."""
    updater = Updater(TELEGRAM_TOKEN)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if not check_tokens:
        raise KeyError('WRONG_TOKENS')
    while True:
        try:
            response = get_api_answer(current_timestamp)
            for homework in check_response(response):
                send_message(bot, parse_status(homework))
            current_timestamp = int(time.time())

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        updater.dispatcher.add_handler(CommandHandler('start', wake_up))
        updater.start_polling()
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
