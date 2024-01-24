


<p align="center">
    <a href="https://pypi.org/project/streamlit-pydantic/" title="PyPi Version"><img src="https://img.shields.io/pypi/v/streamlit-pydantic?color=green&style=flat"></a>
    <a href="https://pypi.org/project/streamlit-pydantic/" title="Python Version"><img src="https://img.shields.io/badge/Python-3.7%2B-blue&style=flat"></a>
    <a href="https://github.com/lukasmasuch/streamlit-pydantic/blob/main/LICENSE" title="Project License"><img src="https://img.shields.io/badge/License-MIT-green.svg"></a>
    <a href="https://twitter.com/lukasmasuch" title="Follow on Twitter"><img src="https://img.shields.io/twitter/follow/lukasmasuch.svg?style=social&label=Follow"></a>
</p>


[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://github.com/tatsu-lab/stanford_alpaca/blob/main/LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/release/python-311/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# Keep in touch with you grandma via Whatsapp - even if she doesn't have a phone 👵🏼

WhatsGranny is a whatsapp tool that enables easy communication with people who cannot use whatsapp and prefer pen and paper. Share your thoughts via voice message and WhatsGranny will summarise them as a letter and send it to your loved one by mail.

# About

WhatsGranny uses the [Twilio](https://www.google.com/search?q=twilio+api+whatsapp) for messaging via whatsapp, [Whisper](https://github.com/openai/whisper) for transcription, and GPT for summarisation.

# Feature roadmap

## Current priority

### Have a working MVP for a single voice memo
- [ ] Rearrange folder structure
- [ ] Write tests for the intelligence module
- [ ] Move to whisper API instead of self-hosting
- [ ] Ideally only run with one service (no task-queue)
- [ ] User can delete address
- [ ] User can manually change message and send it back for mailing

### Crucial improvements
- [ ] User can manually change message and send it back for mailing
- [ ] User can delete address

### Future features

- [ ] User signup
- [ ] User can add photos to message
- [ ] Change from pip to poetry
- [ ] Configure launch.json file for faster debugging requests (flask app is launched and then another script is called)

# Installation / setup instructions

## First time instructions

If you want to run the app yourself then follow these instructions.

First, create a [Twilio](https://www.google.com/search?q=twilio+api+whatsapp) account. This is free initially. Add your Account SID and Auth Token to the .env file in the directory. Have a look at the example .env file to see what else you need to add.

You will need Ngrok to interact with the app from whatsapp while you're running it locally. You can find installation instructions [here](https://ngrok.com/docs/getting-started/). Run the following command to start Ngrok.

`ngrok http 5000`

In your Twilio account, add the url provided by twilio, followed by a `/message` to the Sandbox Configuration post-request address.

![twilio sandbox settings](./readme-images/twilio-sandbox.png)

Run the database using docker-compose. This command will pull the necessary images and start the containers in the background. Run without -d to start the container in the foreground.

`docker-compose up -d`



### GCP

Memos and pdfs can be stored locally, but to send attachments to users via twilio the respective attachment needs to be made available at a publicly accessible url at least for a short time. Since this is not possible with local files you need at least some online solution. This repo uses GCP. You can of course implement another solution but for now GCP presumably is the easiest way to get the repo running as the code is alraedy implemented.

Create service account credentials using the instructions [here](https://cloud.google.com/iam/docs/keys-create-delete#iam-service-account-keys-create-console) and place them in the server folder
run these commands:
```
gcloud config set project grannymail
gcloud iam service-accounts create general-sa --description="general service account for the app" --display-name="general_sa_display_name"
gcloud iam service-accounts keys create gcloud_private_key.json --iam-account=general-sa@grannymail.iam.gserviceaccount.com
gcloud projects add-iam-policy-binding grannymail \
    --member="serviceAccount:general-sa@grannymail.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
```

Set the `GOOGLE_APPLICATION_CREDENTIALS`environment variable to the location of your json file.

You can see alterntive options for authentication, such as using your console to grant automatic access for apps running on your computer (not docker) [here](https://cloud.google.com/docs/authentication/provide-credentials-adc#how-to).


## Quickstart

1. Send "join military-rapidly" to Twilio
2. `ngrok http 5000` -> Copy the url into the twilio console, appending `/message`
3. `make dev`
4. Start debugging the server with VS Code debug

# Pinned resources

Some links to resources that I frequently access during development

- [docker compose documentation](https://docs.docker.com/engine/reference/commandline/compose_up/)
- [Black code formatting docs](https://black.readthedocs.io/en/stable/getting_started.html)
- [python-mariadb-connector](https://www.digitalocean.com/community/tutorials/how-to-store-and-retrieve-data-in-mariadb-using-python-on-ubuntu-18-04)
- [pigar](https://github.com/damnever/pigar) for creation of requirements.txt files `pigar gen -f docker/server/requirements.txt docker/server`

# Some learnings

Check own code for security issues
`bandit example.py`
`bandit -r .`

Check packages for security issues
`safety check`
`safety check --full-report`

# Telegram configuration

1. Setup your own Telegram bot using [BotFather](https://telegram.me/BotFather)
2. Set your Webhook URL by calling this URL: https://api.telegram.org/bot{my_bot_token}/setWebhook?url={url_to_send_updates_to}


# Development setup

1. Download Ngrok and run your development server with `ngrok http https://localhost:80 --domain=adapted-earwig-duly.ngrok-free.app`


### Advice from myself after completing this project to myself before starting this project
- Use render.com to run the bot as a docker container vs. Cloud Run. The continuous deployment with google cloud run is a huge pain and super easy with render.com


# Contributing

## pre-commit

This repo uses pre-commit to run some checks before committing. You can install it with `pip install pre-commit`. Then run `pre-commit install` to install the hooks. You can run the checks manually with `pre-commit run --all-files`.
