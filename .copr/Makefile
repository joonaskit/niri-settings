# COPR "make srpm" entry point: builds a source RPM from the checked-out commit.
#   make -f .copr/Makefile srpm outdir=OUT
# Also works locally (needs git and rpm-build).

spec    := packaging/niri-settings.spec
top     := $(shell git rev-parse --show-toplevel)
version := $(shell sed -n 's/^Version:[[:space:]]*//p' $(top)/$(spec))
outdir  ?= $(top)/dist
work    := $(shell mktemp -d)

srpm:
	git -C $(top) config --global --add safe.directory $(top) || true
	git -C $(top) archive --format=tar.gz --prefix=niri-settings-$(version)/ \
	    -o $(work)/niri-settings-$(version).tar.gz HEAD
	rpmbuild -bs $(top)/$(spec) --define "_sourcedir $(work)" --define "_srcrpmdir $(outdir)"
	rm -rf $(work)

.PHONY: srpm
