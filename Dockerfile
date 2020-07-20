FROM python:3.7

ARG FIREBASE_TOKEN
ARG PROJECT_ID

WORKDIR /usr/src/app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN curl -sL https://deb.nodesource.com/setup_10.x | bash - \
    && apt-get install -y nodejs

RUN npm install -g firebase-tools

RUN firebase firestore:delete --token $FIREBASE_TOKEN --all-collections --project $PROJECT_ID -y

CMD [ "pytest" ]
