# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SOURCEDIR     = source
BUILDDIR      = _build
PUBLISHTMPDIR = /tmp/picotool-pages

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

# Publish to Github Pages.
publish: html
	git clone -b gh-pages git@github.com:dansanderson/picotool.git "$(PUBLISHTMPDIR)"
	cp -rv "$(BUILDDIR)/html/." "$(PUBLISHTMPDIR)"
	git -C "$(PUBLISHTMPDIR)" add .
	git -C "$(PUBLISHTMPDIR)" status
	git -C "$(PUBLISHTMPDIR)" commit -am "Publishing update `date`"
	git -C "$(PUBLISHTMPDIR)" push
	rm -rvf "$(PUBLISHTMPDIR)"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
