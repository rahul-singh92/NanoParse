.PHONY: train up down

SUBSET ?= 0
VERSION ?= v1
SEED ?= 42
MODEL_VERSION ?= v1

train:
	SUBSET=$(SUBSET) python training/train.py --subset $(SUBSET) --version $(VERSION) --seed $(SEED)

up:
	@MODEL_VERSION=$(MODEL_VERSION) bash scripts/deploy.sh

down:
	@bash scripts/destroy.sh

