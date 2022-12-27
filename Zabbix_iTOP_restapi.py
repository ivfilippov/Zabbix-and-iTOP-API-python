#!/usr/bin/python3

# Created on 15.10.2021
# @author: ifilippov

import json
import datetime
import requests
import warnings
import sys
import logging

logging.basicConfig(filename="/tmp/zabbix_iTOP.log", format='%(asctime)s - %(message)s', level=logging.WARNING)
# На всякий случай убираем проверку сертификата
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# Аргументы из zabbix
TITLE = str(sys.argv[1])
DESCRIPTION = str(sys.argv[2])
EVENTDATETIME = str(datetime.datetime.strptime(sys.argv[3], "%Y.%m.%d %H:%M:%S"))
STATUS = str(sys.argv[4])

# Конфиг
ITOP_URL = 'https://itsm.tskad.ru'
ITOP_USER = ''
ITOP_PWD = ''
TICKET_CLASS = "Incident"
ORG_ID = 4  # Организация "ЦКАД"
CALL_ID = 230  # Инициатор "Мониторинг Zabbix"
SERV_ID = 10  # Услуга "Событие из заббикс"
SUBCAT_01 = 10  # Категория "Событие на основании системы мониторинга"
SUBCAT_02 = 8  # Подкатегория "Инцидент"
TEAM_ID = 668  # Команда "Отдел ОУиМ"
AGENT_ID = 112  # Агент "Общая очередь"


# Форматируем ключ для поиска инцидента
KEY = f'SELECT {TICKET_CLASS} WHERE title LIKE "{TITLE}" AND status NOT IN ("closed", "resolved")'


def request_i_top(json_data):
    # Отправляем запрос API iTOP, сформированный в других функциях
    try:
        encoded_data = json.dumps(json_data)
        r = requests.post(ITOP_URL + '/webservices/rest.php?version=1.3',
                          data={'auth_user': ITOP_USER, 'auth_pwd': ITOP_PWD, 'json_data': encoded_data})
        result = json.loads(r.text)
        return result
    except Exception as err:
        logging.exception(err)
        sys.exit()


def check_ticket(KEY):
    # Ищем инцидент по хосту и триггеру в поле "Название" среди открытых инцидентов
    try:
        json_data = {
            'operation': 'core/get',
            'class': TICKET_CLASS,
            'key': KEY,
            'output_fields': "id"
        }
        req_iTOP_raw = request_i_top(json_data)  # Отправляем запрос

        if req_iTOP_raw['objects'] is not None:
            req_itop_objects = request_i_top(json_data)[
                'objects']  # Если есть то ищем ID инцедента, вытаскиваем 'objects'
            json_key = list(req_itop_objects)[0]  # Узнаем ключ(он разный и зависит от id)
            req_itop = req_itop_objects[json_key]['fields']['id']  # Идем по дереву json до самого id
            return req_itop

        else:
            return 'No incident found'
    except Exception as err:
        logging.exception(err)
        sys.exit()


def create_ticket(TITLE, DESCRIPTION, EVENTDATETIME):
    # Создаем инцидент, если он не найден на 1 шаге
    try:
        json_data = {
            'operation': 'core/create',
            'class': TICKET_CLASS,
            'comment': "Zabbix",
            'fields': {
                'title': TITLE,
                'description': DESCRIPTION,
                'org_id': ORG_ID,
                "caller_id": CALL_ID,
                "service_id": SERV_ID,
                "servicesubcategory_id": SUBCAT_01,
                "servicesubcategory2_id": SUBCAT_02,
                "outage_start_date": EVENTDATETIME,
                "team_id": TEAM_ID,
                "agent_id": AGENT_ID,
                # "roadequipment_list": [{"roadequipment_id": KE}]
            },
            'output_fields': 'id',
        }
        req_iTOP = request_i_top(json_data)

        return req_iTOP
    except Exception as err:
        logging.exception(err)
        sys.exit()


def update_ticket(id, DESCRIPTION, STATUS, EVENTDATETIME, EVENTDATETIMECLOSE=""):
    # Обновляем инцидент, если он найден на 1 шаге
    ADDCOMMENT = f"{DESCRIPTION}: {STATUS} ({EVENTDATETIME})"
    try:
        json_data = {
            'operation': 'core/update',
            'class': TICKET_CLASS,
            'comment': "Zabbix",
            'key': id,
            'fields': {
                "public_log": ADDCOMMENT,
                "outage_end_date": EVENTDATETIMECLOSE
            },
            'output_fields': 'id',
        }
        req_iTOP = request_i_top(json_data)
        return req_iTOP
    except Exception as err:
        logging.exception(err)
        sys.exit()


if __name__ == "__main__":
    try:
        incidente_id = check_ticket(KEY)

        if incidente_id == 'No incident found' and STATUS == "OK":
            sys.exit('incident was closed by the operator and not update')

        if incidente_id == 'No incident found' and STATUS == "PROBLEM":
            create_ticket(TITLE, DESCRIPTION, EVENTDATETIME)
            print('incident_create')

        elif STATUS == "OK" and incidente_id is not 'No incident found':
            EVENTDATETIMECLOSE = EVENTDATETIME
            update_ticket(incidente_id, DESCRIPTION, STATUS, EVENTDATETIME, EVENTDATETIMECLOSE)
            print('incident_update OK')

        elif STATUS == "PROBLEM":
            update_ticket(incidente_id, DESCRIPTION, STATUS, EVENTDATETIME)
            print('incident_update PROBLEM')

    finally:
        sys.exit()
