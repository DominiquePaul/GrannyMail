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
db_up:
	cd database_config && supabase start && cd ..
db_down:
	cd database_config && supabase stop && cd ..
db_status:
	cd database_config && supabase status && cd ..
db_sync:
	echo "This will take 75-120 seconds..."
	cd database_config && snaplet snapshot create && sleep 60 && snaplet snapshot restore --no-reset --latest -y && cd ..
