from flask import Flask
import re
from helpers import *
from firebase_admin import firestore, _apps, initialize_app, credentials
from google.cloud.storage import Client
from google.cloud.scheduler_v1 import CloudSchedulerClient
from google.api_core.exceptions import NotFound, GoogleAPICallError, PermissionDenied


app = Flask(__name__)


@app.route('/health')
def health_check():
    return "200 OK"


@app.route('/init')
def start_process():
    start_time = time()
    storage_client = Client()
    scheduler_client = CloudSchedulerClient()
    scheduler_path = scheduler_client.location_path(config.PROJECT_ID, config.REGION_ID)
    cred = credentials.ApplicationDefault()

    try:
        scheduler_client.delete_job(f"{scheduler_path}/jobs/{config.CRON_NAME}")
    except GoogleAPICallError or PermissionDenied:
        logging.warning("course-collect manually triggered")

    try:
        scheduler_client.delete_job(f"{scheduler_path}/jobs/forcequit")
    except GoogleAPICallError or PermissionDenied:
        logging.warning("forcequit job does not exist")

    if not _apps:
        initialize_app(cred, {"projectId": config.PROJECT_ID})
        logging.info("initializing firebase")

    firebase_db = firestore.client()

    if storage_client.bucket(config.BUCKET_NAME).exists():
        logging.info("reading from existing bucket")
        coursepickle_bucket = storage_client.bucket(config.BUCKET_NAME)
    else:
        logging.info("creating new bucket")
        coursepickle_bucket = storage_client.create_bucket(config.BUCKET_NAME)

    # Get unfinished course codes
    coursecode_blob = coursepickle_bucket.blob(config.COURSE_CODE_BLOB_NAME)
    try:
        coursecode_raw = coursecode_blob.download_as_string()
        unique_course_codes = pickle.loads(coursecode_raw)
    except NotFound:
        # Fetch course metadata per code for instructor, schedule, time, location, GPA, grade distributions
        all_courses = get_all_courses(firebase_db)
        unique_course_codes = set([course["code"] for course in all_courses.values()])

    # Get existing course metadata
    coursepickle_blob = coursepickle_bucket.blob(config.COURSE_METADATA_BLOB_NAME)
    try:
        course_metadata_raw = coursepickle_blob.download_as_string()
        course_metadata = pickle.loads(course_metadata_raw)
    except NotFound:
        course_metadata = {}

    course_metadata = course_metadata if course_metadata else {}

    # Conform to free tier limits (looks like {"runtime": 123, "datetime": datetime(...)}
    last_modified_blob = coursepickle_bucket.blob(config.LAST_MODIFIED_BLOB_NAME)
    try:
        last_modified_raw = last_modified_blob.download_as_string()
        last_modified = pickle.loads(last_modified_raw)
    except NotFound:
        last_modified = {}

    last_modified = last_modified if last_modified else {
        "runtime": 0,
        "datetime": None
    }

    check_free_tier_force_exit(scheduler_client, scheduler_path, get_curr_runtime(last_modified["runtime"], start_time))
    if last_modified["datetime"] and last_modified["datetime"].day < datetime.now().day:
        last_modified["runtime"] = 0

    if bool(int(config.UPDATE_EXTRA_FIELDS)):
        course_code_done = []
        for code in unique_course_codes:
            try:
                logging.info(f"Checking class {code}")
                print(code)
                split_code = code.split()
                pg = requests_connectionerror_bypass(config.SCHEDULE_TARGET_URL_FMT, [config.LATEST_TERM, *split_code], scheduler_client, scheduler_path, last_modified, start_time)

                html_content = requests_bandwith_bypass(pg, config.SCHEDULE_TARGET_URL_FMT, split_code, scheduler_client, scheduler_path, last_modified, start_time)

                class_ddtitle = html_content.find_all("th", {"scope": "colgroup"}, class_="ddtitle")

                class_titles = [th.a.text for th in class_ddtitle if "table" in str(th.find_next("tr"))]

                class_dddefaults = [str(c).replace("\n", "") for c in html_content.find_all("td", class_="dddefault")
                                    if "cc.gatech.edu" in c.text or "students" in c.text or "lecture" in c.text or "Semester" in c.text]

                class_terms = [re.search("(?<=Associated Term: </span>)([a-zA-Z0-9'\s]*)(?=<br)", c).group(0).strip() for c
                               in class_dddefaults]

                class_registration_dates = [
                    re.search("(?<=Registration Dates: </span>)([a-zA-Z0-9,\s]*)(?=<br)", c).group(0).strip() for c in
                    class_dddefaults]

                class_attributes = [
                    re.search("(?<=Attributes: </span>)([^<]*)(?=<br)", c).group(0).strip() if "Attributes" in c else None
                    for c in class_dddefaults]

                class_grade_bases = [re.search("(?<=Grade Basis: </span>)([A-Z0-9\s]*)(?=<br)", c).group(0).strip() for c in
                                     class_dddefaults]

                class_table = html_content.find_all("table", class_="datadisplaytable")[1:-1]

                class_schedule_headers = [["_".join(header.text.lower().split()) for header in table.find_all("th")] for
                                          table in class_table]

                class_schedule_data = [[header.text.replace("(P)", "").strip() for header in table.find_all("td")] for table
                                       in class_table]

                for c in class_schedule_data:
                    c[-1] = " ".join(c[-1].split())

                instructor_emails = [
                    re.search("([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)", str(c)).group(1) if "mailto" in str(
                        c) else None for c in class_table]

                pg = requests_connectionerror_bypass(config.CRITIQUE_TARGET_URL_FMT, split_code, scheduler_client, scheduler_path, last_modified, start_time)

                html_content = requests_bandwith_bypass(pg, config.CRITIQUE_TARGET_URL_FMT, split_code, scheduler_client, scheduler_path, last_modified, start_time)

                critique_table = html_content.find("table", {"id": "dataTable"})

                critique_headers = ["_".join(th.text.lower().split()) for th in critique_table.find_all("th")][1:]

                critique_data_raw = [td.text for td in critique_table.find_all("td")]

                critique_data = [critique_data_raw[x:x + len(critique_headers) + 1] for x in
                                 range(0, len(critique_data_raw), len(critique_headers) + 1)]

                critique_instructors = []
                for i in range(len(critique_data)):
                    critique_instructors.append(" ".join(critique_data[i][0].split(", ")[::-1]))
                    del critique_data[i][0]
                    critique_data[i] = [critique_data[i][0]] + [float(x) for x in critique_data[i][1:]]

                critique_averages = {}

                for i in range(len(critique_instructors)):
                    critique_averages[critique_instructors[i]] = dict(zip(critique_headers, critique_data[i]))

                for i in range(len(class_titles)):
                    try:
                        schedule = dict(zip(class_schedule_headers[i], class_schedule_data[i]))
                    except:
                        print(i)
                        raise RuntimeError

                    course_metadata[class_titles[i]] = {
                        "terms": class_terms[i],
                        "registration_dates": class_registration_dates[i],
                        "attributes": class_attributes[i],
                        "grade_basis": class_grade_bases[i],
                        "schedule": schedule,
                        "instructor_email": instructor_emails[i],
                        "averages": critique_averages[schedule["instructors"]] if schedule["instructors"] in critique_averages else None
                    }

                course_code_done.append(code)
            except RuntimeError as e:
                write_blobs_before_exit(coursepickle_blob, coursecode_blob, last_modified_blob, course_metadata, unique_course_codes, course_code_done, last_modified, start_time)
                schedule_next_try(scheduler_client, scheduler_path)
                raise e


    """
    Fetch per course seat, credit, and requirement information
    """
    for i in range(config.START_IDX, config.END_IDX):
        try:
            logging.info(f"Checking class with id {i}")

            pg = requests_connectionerror_bypass(config.REGISTRATION_TARGET_URL_FMT, [config.LATEST_TERM, i], scheduler_client, scheduler_path, last_modified, start_time)

            html_content = requests_bandwith_bypass(pg, config.REGISTRATION_TARGET_URL_FMT, [i], scheduler_client, scheduler_path, last_modified, start_time)

            if "-" not in html_content.text:
                logging.info(f"skipping {i}")
                continue

            class_general = html_content.find_all("th", {"scope": "row"}, class_="ddlabel")[0].text

            # For classes with dashes in the class name, replace them one by one with spaces
            # TODO retain dashes by using an alternative delimiter like " - "
            while len(re.findall("-", class_general)) != 3:
                class_general = re.sub("-", " ", class_general, 1)

            class_general_delimited = [s.strip() for s in class_general.split("-")]

            class_name = class_general_delimited[0]

            class_id = int(class_general_delimited[1])

            class_code = class_general_delimited[2]

            class_dddefault = " ".join(html_content.find_all("td", class_="dddefault")[0].text.replace("\n", " ").split())

            class_credits = float(re.search("\d+\.\d+(?=\s+Credits)", class_dddefault).group(0))

            class_seats = [int(re.search("Seats (-*\d+) (-*\d+) (-*\d+)", class_dddefault).group(x)) for x in range(1, 4)]

            class_waitlist_seats = [int(re.search("Waitlist Seats (-*\d+) (-*\d+) (-*\d+)", class_dddefault).group(x)) for x
                                    in
                                    range(1, 4)]

            # Regex search method depends on prerequisites and restrictions combination
            if "Prerequisites" in class_dddefault:
                if "Restrictions" in class_dddefault:
                    class_prerequisites = re.search("Prerequisites: (.*)", class_dddefault).group(1)
                    class_restrictions = re.search("Restrictions: (.*) Prerequisites", class_dddefault).group(1)
                else:
                    class_prerequisites = re.search("Prerequisites: (.*)", class_dddefault).group(1)
                    class_restrictions = None
            else:
                if "Restrictions" in class_dddefault:
                    class_prerequisites = None
                    class_restrictions = re.search("Restrictions: (.*)", class_dddefault).group(1)
                else:
                    class_prerequisites = None
                    class_restrictions = None

            course_dict = {
                "id": class_id,
                "code": class_code,
                "name": class_name,
                "credits": class_credits,
                "seats": {
                    "capacity": class_seats[0],
                    "actual": class_seats[1],
                    "remaining": class_seats[2]
                },
                "waitlist": {
                    "capacity": class_waitlist_seats[0],
                    "actual": class_waitlist_seats[1],
                    "remaining": class_waitlist_seats[2]
                },
                "restrictions": class_restrictions,
                "prerequisites": class_prerequisites,
                "last_updated": datetime.now()
            }
            if class_general in course_metadata:
                course_dict.update(course_metadata[class_general])

            # Send all collected class metadata
            firebase_db.collection(u'{}'.format(config.PRIMARY_TABLE_NAME)).document(u'{}'.format(class_id)).set(
                course_dict)

            all_table_name = f"{config.SECONDARY_TABLE_NAME}{i // 500}"
            all_courses_doc = firebase_db.collection(u'{}'.format(all_table_name)).document(
                u'{}'.format("all_courses")).get()
            if all_courses_doc.exists:
                all_courses = all_courses_doc.to_dict()
                all_courses[str(class_id)] = course_dict
                firebase_db.collection(u'{}'.format(all_table_name)).document(
                    u'{}'.format("all_courses")).set(all_courses)
            else:
                firebase_db.collection(u'{}'.format(all_table_name)).document(
                    u'{}'.format("all_courses")).set({
                    str(class_id): course_dict
                })
        except RuntimeError as e:
            write_blobs_before_exit(coursepickle_blob, coursecode_blob, last_modified_blob, course_metadata, [], [], last_modified, start_time)
            schedule_next_try(scheduler_client, scheduler_path)
            raise e

    # Delete all blobs
    coursepickle_blob.delete()
    coursecode_blob.delete()
    last_modified_blob.delete()
    schedule_next_try(scheduler_client, scheduler_path, adjust_cron=timedelta(days=1))
    return "200 OK"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
