setup_repo:
	virtualenv venv
	source venv/bin/activate
	pip install -r requirements.txt
ngrok:
	ngrok http http://localhost:8000 --domain=adapted-earwig-duly.ngrok-free.app
devbot:
	gunicorn grannymail.telegrambot:app -k uvicorn.workers.UvicornWorker --reload --timeout=0
bot:
	gunicorn telegrambot:app -k uvicorn.workers.UvicornWorker -b :8000 --workers 1 --threads 8 --timeout 0
