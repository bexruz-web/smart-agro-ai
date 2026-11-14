# Smart Agro AI — tez-tez ishlatiladigan buyruqlar. `make help`
COMPOSE = docker compose
PROD = docker compose -f docker-compose.yml -f docker-compose.prod.yml
API_URL ?= http://localhost:$${WEB_PORT:-80}/api/v1

.PHONY: help up up-prod down logs ps migrate seed bootstrap test smoke demo-drought demo-rain demo-fault demo-normal sim backup restore-check

help:
	@echo "make up            — barcha servislarni ishga tushirish (HTTP, lokal/test)"
	@echo "make up-prod       — HTTPS bilan (docker-compose.prod.yml, sertifikat kerak)"
	@echo "make seed          — DEMO fermer, 2 dala, 2 qurilma (tokenlar simulator/devices.json'ga)"
	@echo "make bootstrap     — demo dalalar uchun NASA POWER iqlim tarixi + prognoz + birinchi tahlil"
	@echo "make test          — backend unit testlari"
	@echo "make smoke         — ishlab turgan API'ga qarshi to'liq smoke test"
	@echo "make demo-drought  — simulyator: qurg'oqchilik (tuproq namligi tushadi -> ogohlantirish)"
	@echo "make logs / ps / down / backup"

up:
	$(COMPOSE) up -d --build

up-prod:
	$(PROD) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail 100

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api alembic upgrade head

seed:
	$(COMPOSE) exec -u 0 api sh -c "python -m app.scripts.seed_demo --devices-file /simulator/devices.json $(if $(TG),--telegram-id $(TG),) && chown $$(id -u):$$(id -g) /simulator/devices.json"

bootstrap:
	$(COMPOSE) exec worker python -m app.scripts.bootstrap_all

test:
	docker build -q -f backend/Dockerfile --build-arg INSTALL_DEV=true -t smartagro-backend-test . && \
	docker run --rm --network none smartagro-backend-test python -m pytest -q -p no:cacheprovider

smoke:
	$(COMPOSE) cp backend/tests/smoke_api.py api:/tmp/smoke_api.py && $(COMPOSE) exec -T api python /tmp/smoke_api.py

demo-drought:
	python3 simulator/sim.py --api $(API_URL) --scenario drought --interval 10 --count 12

demo-rain:
	python3 simulator/sim.py --api $(API_URL) --scenario heavy_rain --interval 10 --count 12

demo-fault:
	python3 simulator/sim.py --api $(API_URL) --scenario sensor_fault --interval 10 --count 12

demo-normal:
	python3 simulator/sim.py --api $(API_URL) --scenario normal --interval 15

backup:
	$(COMPOSE) exec db sh -c 'pg_dump -U $$POSTGRES_USER $$POSTGRES_DB' | gzip > backups/manual-$$(date +%Y%m%d-%H%M).sql.gz
