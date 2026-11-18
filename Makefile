.PHONY: build up down once export logs test config

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

once:
	docker compose run --rm monitor once

export:
	docker compose exec monitor netwatch export --output /exports/network-results.csv

logs:
	docker compose logs -f monitor

test:
	docker build --target test -t home-network-monitor-test .

config:
	docker compose config
