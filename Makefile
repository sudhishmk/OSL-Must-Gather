CONTAINER_ENGINE ?= podman
IMAGE ?= localhost/osl-must-gather:1.39-dev
OPENSHIFT_VERSION ?= 4.19
SHELLCHECK ?= shellcheck

.PHONY: help build push lint test clean
help:
	@printf '%s\n' 'build: build IMAGE with CONTAINER_ENGINE' 'push: publish IMAGE (explicit)' 'lint: ShellCheck and Bash syntax' 'test: offline regression tests' 'clean: remove only IMAGE'
build:
	$(CONTAINER_ENGINE) build --build-arg OPENSHIFT_VERSION=$(OPENSHIFT_VERSION) -t $(IMAGE) .
push:
	$(CONTAINER_ENGINE) push $(IMAGE)
lint:
	$(SHELLCHECK) --severity=style collection-scripts/gather
	bash -n collection-scripts/gather
test:
	PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
clean:
	$(CONTAINER_ENGINE) image rm $(IMAGE)
