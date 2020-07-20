import os

DEFAULT_PROJECT_ID = os.environ.get("DEFAULT_PROJECT_ID")
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION_ID = os.environ.get("APP_REGION")
UPDATE_EXTRA_FIELDS = os.environ.get("UPDATE_EXTRA_FIELDS")

TIME_ZONE = "America/New_York"
CRON_NAME = "auto-trigger-collect"
BUCKET_NAME = "coursepickle"
COURSE_METADATA_BLOB_NAME = "courses"
LAST_MODIFIED_BLOB_NAME = "last_modified"
COURSE_CODE_BLOB_NAME = "course_codes"
EIGHT_HOURS_AND_FIFTY_MINUTES = (8 * 60 + 50) * 60
FIFTY_FIVE_MINUTES = 55 * 60
FIVE_MINUTES = 5 * 60

PRIMARY_TABLE_NAME = "CLASSES_MASTER"

SECONDARY_TABLE_NAME = "CLASSES_ALL"

LATEST_TERM = "202008"

START_IDX = 80007

END_IDX = 93437

REGISTRATION_TARGET_URL_FMT = "https://oscar.gatech.edu/pls/bprod/bwckschd.p_disp_detail_sched?term_in={}&crn_in={}"

SCHEDULE_TARGET_URL_FMT = "https://oscar.gatech.edu/pls/bprod/bwckctlg.p_disp_listcrse?term_in={}&subj_in={}&crse_in={}&schd_in=%"

CRITIQUE_TARGET_URL_FMT = "https://critique.gatech.edu/course.php?id={}%20{}"