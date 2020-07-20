.                     |.
:--------------------:|:--------------------:
![GTCC](docs/gt.png)  |![GCP](docs/gcloud.png)



# course_collect

Self-triggering batch process that populates Firestore database with data aggregated from [Oscar](https://oscar.gatech.edu),
[Course Critique](https://critique.gatech.edu).

[![Build Status](https://travis-ci.org/aubrey-y/course_collect.svg?branch=master)](https://travis-ci.org/aubrey-y/course_collect)
![GitHub top language](https://img.shields.io/github/languages/top/aubrey-y/course_collect)

## Setup

### Linux

1. Set up virtualenv with `python3 -m venv venv` (I have `python3` aliased to `python`)
2. If you want to configure PyCharm to recognize the folder `venv/` as your project interpreter, manually add the
interpreter (else skip this step)

    a) File -> Settings -> Project -> Project Interpreter
    
    b) settings cog -> Add...
    
    c) Choose your environment type (mine is WSL) -> ...
    
    d) `...\course_collect\venv\bin\python`

3. Run `source venv/bin/activate` to make sure `python`(3) and `pip`(3) are pointing to your virtual environment and not
your global installations

4. Run `pip list` to make sure you're looking at a new environment

5. Run `pip install -r requirements.txt`

6. Find and set all necessary environment variables (including 
[`GOOGLE_APPLICATION_CREDENTIALS`](https://cloud.google.com/docs/authentication/getting-started), and
[`FIREBASE_TOKEN`](https://firebase.google.com/docs/cli#cli-ci-systems) for continuous integration)

7. Run `gunicorn app:app --timeout 3600` or through PyCharm (I recommend PyCharm because you can more flexibly configure environment variables
via your run configuration)

## Usage

To run the app locally, simply run the flask app and make a GET request to
[localhost:8000/init](https://localhost:8000/init) to trigger the batch process.

## Deployment

### Local

Make sure you have the `gcloud` cli installed and set up. Make a copy of `app.template.yaml` in the same directory but
rename it to `app.yaml` which is gitignored, so you don't have to worry about committing sensitive data. Procure and
fill in your environment variables and deploy via `gcloud app deploy app.yaml`.

### Virtual

Travis CI's configuration installs the `gcloud` cli, authenticates by decrypting `credentials.tar.gz.enc`, and automates
the creation of `app.yaml` before deploying using Linux's `envsubst` command and creating `app.yaml` with the
system-configured environment variables, which is a clever way of protecting secrets with Google App Engine, which has
ignored requests for years to allow direct configuration of environment variables on an App Engine service not unlike
what already exists for Cloud Functions, for example.
