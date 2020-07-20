import config
import requests
import pickle
import logging
from time import sleep, time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


def requests_connectionerror_bypass(url, params, scheduler_client, scheduler_path, last_modified, start_time):
    pg = None

    sub_start_time = time()
    while not pg:
        try:
            pg = requests.get(url.format(*params))
        except requests.exceptions.ConnectionError:
            sleep(5)

        check_request_timeout_force_exit(scheduler_client, scheduler_path, time() - sub_start_time, url)
        check_idle_timeout_limitation(scheduler_client, scheduler_path, start_time)

    check_free_tier_force_exit(scheduler_client, scheduler_path, get_curr_runtime(last_modified["runtime"], start_time))
    return pg


def requests_bandwith_bypass(pg, url, params, scheduler_client, scheduler_path, last_modified, start_time):
    html_content = BeautifulSoup(pg.content, "html.parser")

    sub_start_time = time()
    if "exceeded the bandwidth limits" in html_content.text:
        while "exceeded the bandwidth limits" in html_content.text:
            sleep(60)
            pg = requests.get(url.format(config.LATEST_TERM, *params))
            html_content = BeautifulSoup(pg.content, "html.parser")

            check_request_timeout_force_exit(scheduler_client, scheduler_path, time() - sub_start_time, url)
            check_idle_timeout_limitation(scheduler_client, scheduler_path, start_time)

    check_free_tier_force_exit(scheduler_client, scheduler_path, get_curr_runtime(last_modified["runtime"], start_time))
    return html_content


def fetch_proxies(ua):
    proxy_pg = requests.get("https://www.sslproxies.org/", headers={"User-Agent": ua.random})

    proxies = []

    proxy_bs = BeautifulSoup(proxy_pg.content, 'html.parser')
    proxies_table = proxy_bs.find(id='proxylisttable')

    for row in proxies_table.tbody.find_all('tr'):
        proxies.append({
            'ip': row.find_all('td')[0].string,
            'port': row.find_all('td')[1].string
        })

    return proxies


def get_all_courses(firebase_db):
    final_dict = {}
    for i in range(config.START_IDX//500, config.END_IDX//500):
        all_courses_doc = firebase_db.collection(u'{}'.format(config.SECONDARY_TABLE_NAME) + str(i)).document(
            u'{}'.format("all_courses")).get()
        if all_courses_doc.exists:
            final_dict.update(all_courses_doc.to_dict())
        else:
            break
    return final_dict


def get_curr_runtime(initial_time, start_time):
    return time() - start_time + initial_time


def check_free_tier_force_exit(scheduler_client, scheduler_path, curr_runtime):
    if curr_runtime > config.EIGHT_HOURS_AND_FIFTY_MINUTES:
        schedule_next_try(scheduler_client, scheduler_path)
        raise RuntimeError(f"FREE TIER DEPLETED: {curr_runtime} used so far, over acceptable limit")


def check_idle_timeout_limitation(scheduler_client, scheduler_path, start_time):
    if time() - start_time > config.FIFTY_FIVE_MINUTES:
        schedule_next_try(scheduler_client, scheduler_path)
        raise RuntimeError(f"IDLE TIMEOUT: passed 55m mark, no longer safe to continue")


def get_next_cron_expr(adjust_cron=None):
    now = datetime.now()
    now + timedelta(hours=1)
    if adjust_cron:
        now += adjust_cron
    return f"{int(now.minute)} {int(now.hour)} {int(now.day)} {int(now.month)} *"


def check_request_timeout_force_exit(scheduler_client, scheduler_path, curr_runtime, url):
    if curr_runtime > config.FIVE_MINUTES:
        schedule_next_try(scheduler_client, scheduler_path)
        raise RuntimeError(f"REQUEST TIMEOUT: {url} down for 5+ minutes")


def write_blobs_before_exit(course_blob, course_code_blob, last_modified_blob, course_metadata, unique_course_codes, course_code_done, last_modified, start_time):
    course_blob.upload_from_string(pickle.dumps(course_metadata))
    course_code_blob.upload_from_string(pickle.dumps([code for code in unique_course_codes if code not in course_code_done]))
    last_modified_blob.upload_from_string(pickle.dumps({
        "runtime": last_modified["runtime"] + (time() - start_time),
        "datetime": datetime.now()
    }))


def schedule_next_try(scheduler_client, scheduler_path, adjust_cron=None):
    logging.info("scheduling next try")
    scheduler_client.create_job(scheduler_path, {
        "name": f"{scheduler_path}/jobs/{config.CRON_NAME}",
        "app_engine_http_target": {"relative_uri": "/init", "http_method": "GET", "app_engine_routing": {"service": "course-collect"}},
        "time_zone": config.TIME_ZONE,
        "schedule": get_next_cron_expr(adjust_cron)
    })
    scheduler_client.create_job(scheduler_path, {
        "name": f"{scheduler_path}/jobs/forcequit",
        "app_engine_http_target": {"relative_uri": "/_ah/stop", "http_method": "GET", "app_engine_routing": {"service": "course-collect"}},
        "time_zone": config.TIME_ZONE,
        "schedule": get_next_cron_expr(-timedelta(minutes=58))
    })
