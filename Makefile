setup_repo:
	virtualenv venv
	source venv/bin/activate
	pip install -r requirements.txt
ngrok:
	ngrok http https://localhost:8081 --domain=adapted-earwig-duly.ngrok-free.app --host=
devbot:
	cd grannymail && gunicorn telegrambot:app -k uvicorn.workers.UvicornWorker --reload




	