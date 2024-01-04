setup_repo:
	virtualenv venv
	source venv/bin/activate
	pip install -r requirements.txt
encrypt:
	# Encrypting files
	gcloud kms encrypt --plaintext-file=.env --ciphertext-file=.env.enc --location=europe-west1 --keyring=goldenbook_key --key=goldenbook_key
	gcloud kms encrypt --plaintext-file=dev.env --ciphertext-file=dev.env.enc --location=europe-west1 --keyring=goldenbook_key --key=goldenbook_key
	gcloud kms encrypt --plaintext-file=prod.yaml --ciphertext-file=prod.yaml.enc --location=europe-west1 --keyring=goldenbook_key --key=goldenbook_key
convert_yamls:
	python scripts/yaml_to_env.py
dev:
	docker compose -f "docker-compose.debug.yml" up --build
