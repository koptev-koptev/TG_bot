import logging
import os
import time
import json
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

logging.basicConfig(level=logging.INFO,
                    filename='main.log',
                    format='%(asctime)s, %(levelname)s, %(message)s')

logger = logging.getLogger(__name__)

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка что все токены заданы."""
    token_list = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    ]
    if not all(token_list):
        message = 'Отсутствует или не задан токен'
        logger.critical(message)
        return False
    return True


def send_message(bot, message):
    """Проверка отправки сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение доставлено')
    except telegram.TelegramError(message):
        raise TelegramError('Не удалось отправить сообщение')


def get_api_answer(timestamp):
    """Проверка получения ответа от API."""
    timestamp = int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logger.info('Получен ответ от API')
        if response.status_code != HTTPStatus.OK:
            raise ConnectionError(f'Неожиданный ответ сервиса'
                                  f'{response.status_code}')
        return response.json()
    except json.decoder.JSONDecodeError:
        logger.error('Формат ответа не json')
    except requests.exceptions.RequestException as error:
        logger.error(f'Ошибка при обращении к API: {error}')


def check_response(response):
    """Проверка ответа от API на корректность."""
    if type(response) is not dict:
        message = 'Ответ API не словарь'
        logger.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        raise TypeError('Ответ не содержит информации о домашних работах')
    if 'current_date' not in response:
        raise TypeError('Ответ не содержит информации о домашних работах')
    if len(response['homeworks']) == 0:
        return []
    if type(response['homeworks']) is not list:
        raise TypeError('Содержимое [homeworks] не список')
    homework = response['homeworks']
    return homework


def parse_status(homework):
    """Извлекает из информации о конкретной."""
    """домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        logger.error('В ответе API не содержится ключ homework_name.')
        raise KeyError(
            'В ответе API не содержится ключ homework_name.'
        )

    if 'status' not in homework:
        logger.error('В ответе API не содержится ключ status.')
        raise KeyError('В ответе API не содержится ключ status.')

    if homework['status'] not in HOMEWORK_VERDICTS:
        raise KeyError('ошибка статуса')

    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[homework_status]

    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return message


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    if not check_tokens():
        return
    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            homework_list = check_response(response)
            if homework_list:
                message = parse_status(homework_list[0])
                send_message(bot, message)
            timestamp = response['current_date']
            time.sleep(RETRY_PERIOD)
        except json.decoder.JSONDecodeError:
            logger.error('Формат ответа не json')
        except requests.exceptions.RequestException as error:
            logger.error(f'Ошибка при обращении к API: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(error)
            send_message(bot, f'{error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
