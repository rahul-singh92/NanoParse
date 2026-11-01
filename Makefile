.PHONY: train

SUBSET ?= 0
VERSION ?= v1
SEED ?= 42

train:
	SUBSET=$(SUBSET) python training/train.py --subset $(SUBSET) --version $(VERSION) --seed $(SEED)