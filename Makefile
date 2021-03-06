# -*- coding: utf-8 -*-

# all files in this repo are expected to be utf-8
# for transcoding, use e.g. 
#     recode ISO-8859-15..UTF-8 <filename>

all: 
.PHONY: all

WEEKS=$(wildcard W?) 

# for phony targets
force:

#
tags: force
	git ls-files | xargs etags
.PHONY: tags

# run nbnorm on all notebooks
norm normalize: normalize-notebook normalize-quiz

# add the --sign option only on Thierry's macos to reduce noise-only changes
NORM = tools/nbnorm.py
#UNAME := $(shell uname)
#ifeq ($(UNAME),Darwin)
#NORM_OPTIONS = --sign
#endif

normalize-nb normalize-notebook: force
	find W[0-9]* -name '*.ipynb' | fgrep -v '/.ipynb_checkpoints/' | xargs $(NORM) $(NORM_OPTIONS)

normalize-quiz: force
	find W[0-9]* -name '*.quiz' | xargs tools/quiznorm.py

all: norm

.PHONY: norm normalize normalize-nb normalize-notebook normalize-quiz

#
CLEAN_FIND= -name '*~' -o -name '.\#*' -o -name '*pyc'

toclean: force
	find . $(CLEAN_FIND) -print0 | xargs -0 ls

clean:: force
	find . $(CLEAN_FIND) -name '*~' -o -name '.#*' -print0 | xargs -0 rm -f

#################### corriges
all: corriges
corriges:
	$(MAKE) -C corriges

corriges-pdf:
	$(MAKE) -C corriges pdf

corriges-clean:
	$(MAKE) -C corriges clean

.PHONY: corriges corriges-pdf corriges-clean 

########################################
# historical note
# students asked for an alternate format for notebooks
# (*) at the beginning we went for a PDF approach, generating
# markdown and then using gitprint
# this resulted in a lot of approximate - if at all correct - output
# (*) I then tried to use latex -> pdf, which is better now that
# we don't use rawnbconvert anymore; result was more reliable,
# but really not nice to look at - in other words
# it would require a lot of styling, I'm thinking
# a complete latex document class to have something decent
# (*) so finally I came to consider html output as the most
# reliable + pretty-to-look-at approach
#
# the other ones probably still work; note that the
# gitprint thing has the additional drawback
# that you need to commit the markdown files first up to github
# before you can use gitprint, which makes things a little awkward

# I'm removing the 2 pdf subdirs from git

########################################

# list of notebooks
NOTEBOOKS = $(wildcard W*/W*S[0-9]*.ipynb)

BRANCH=master
GITPRINT_URL_ROOT = https://gitprint.com/parmentelat/flotpython/blob/$(BRANCH)/

# simple basename
define sbn
$(basename $(notdir $(1)))
endef

define markdown_location
markdown/$(call sbn,$(1)).md
endef

define html_location
html/$(call sbn,$(1)).html
endef

define pdflatex_location
pdf-latex/$(call sbn,$(1)).pdf
endef

define gitprint_location
pdf-gitprint/$(call sbn,$(1)).pdf
endef
define gitprint_url
$(GITPRINT_URL_ROOT)/markdown/$(call sbn,$(1)).md?download
endef

MARKDOWNS = $(foreach notebook,$(NOTEBOOKS),$(call markdown_location,$(notebook)))
HTMLS	  = $(foreach notebook,$(NOTEBOOKS),$(call html_location,$(notebook)))
PDFLATEXS = $(foreach notebook,$(NOTEBOOKS),$(call pdflatex_location,$(notebook)))
GITPRINTS = $(foreach notebook,$(NOTEBOOKS),$(call gitprint_location,$(notebook)))

# apply this rule to all notebooks
define notebook_rule
$(call markdown_location,$(1)): $(1)
	ipython nbconvert --to markdown $(1) --stdout > $(call markdown_location,$(1))

$(call html_location,$(1)): $(1)
	(cd html; ln -f -s ../$(1) $(notdir $(1)) ;\
	ipython nbconvert --to html $(notdir $(1));\
	)

$(call pdflatex_location,$(1)): $(1)
	(cd pdf-latex; ln -f -s ../$(1) $(notdir $(1)) ;\
	ipython nbconvert --to latex --post pdf $(notdir $(1));\
	rm $(notdir $(1) $(call sbn,$(1)).tex ))

$(call gitprint_location,$(1)): $(call markdown_location,$(1))
	curl -o $(call gitprint_location,$(1)) $(call gitprint_url,$(1))

$(call sbn,$(1)): $(call markdown_location,$(1)) $(call html_location,$(1)) $(call pdflatex_location,$(1)) $(call gitprint_location, $(1))

.PHONY: $(call sbn,$(1))
endef

$(foreach notebook,$(NOTEBOOKS),$(eval $(call notebook_rule,$(notebook))))

md markdown: $(MARKDOWNS)

md-clean markdown-clean:
	rm -f markdown/*.md

.PHONY: md markdown md-clean markdown-clean
all: md


html: $(HTMLS)

html-clean:
	rm -f html/*.{html,ipynb}

.PHONY: html html-clean
all: html


# the cool thing with this process is we do not need to commit to github first
pdf-latex pdflatex: $(PDFLATEXS)

pdf-latex-clean pdflatex-clean:
	rm -f pdf-latex/*.{aux,out,log,ipynb,tex,pdf}

.PHONY: pdf-latex pdflatex pdf-latex-clean pdflatex-clean

# these need to be done AFTER the markdown have been pushed up to github 
pdf-gitprint gitprint: $(GITPRINTS)

pdf-gitprint-clean gitprint-clean:
	rm -f pdf-gitprint/*.pdf

.PHONY: pdf-gitprint gitprint

# not sure this really is helpful but well
pdf: pdflatex gitprint
.PHONY: pdf

out: html markdown pdflatex gitprint
out-clean: html-clean markdown-clean pdflatex-clean gitprint-clean

.PHONY: out out-clean

##############################
TARS =

TARS += notebooks-html.tar
NOTEBOOKS-HTML = $(foreach notebook,$(NOTEBOOKS),notebooks/$(call sbn,$(notebook)).html)
notebooks-html.tar: force
	ln -f -s html notebooks
	tar -chf $@ notebooks/custom.css $(NOTEBOOKS-HTML)

TARS += notebooks-ipynb.tar
NOTEBOOKS-IPYNB = $(foreach notebook,$(NOTEBOOKS),notebooks/$(call sbn,$(notebook)).ipynb)
notebooks-ipynb.tar: force
	ln -f -s html notebooks
	tar -chf $@ $(NOTEBOOKS-IPYNB)

TARS += corriges.tar
corriges.tar: force
	tar -cf $@ corriges/*.{pdf,txt,py}


#TARS += pdf-gitprint.tar
pdf-gitprint.tar: force
	tar -cf $@ pdf-gitprint/W*pdf

#TARS += pdf-latex.tar
pdf-latex.tar: force
	tar -cf $@ pdf-latex/W*pdf

##########
TGZS = $(subst .tar,.tgz,$(TARS))

%.tgz: %.tar
	gzip -c9 $*.tar > $@

all-tars.tar: $(TGZS)
	tar -cf $@ $(TGZS)

tars: $(TARS) $(TGZS) all-tars.tar

tars-clean:
	rm -f $(TARS) $(TGZS) all-tars.tar

.PHONY: tars tars-clean


##########
GITCOUNT = xargs git ls-files | wc -l
COUNT    = wc -l

check: check-files check-nonw check-w check-html check-ipynb-in-html check-markdown
# check-pdf-latex check-pdf-gitprint

check-files: force
	@echo NOTEBOOKS make variable has $(words $(NOTEBOOKS)) words
	@echo GITPRINTS make variable has $(words $(GITPRINTS)) words

check-nonw: force
	@echo "allow for one more (W2/exo-sample.ipynb)"
	ls W*/*nb | grep -v '/W' | $(GITCOUNT)

check-w: force
	ls W*/W*nb | $(GITCOUNT)

check-html: force
	ls html/W*.html | $(GITCOUNT)

check-ipynb-in-html: force
	ls html/W*.html | $(COUNT)

check-markdown: force
	ls markdown/W*.md | $(GITCOUNT)

check-pdf-latex: force
	ls pdf-latex/W*.pdf | $(GITCOUNT)

check-pdf-gitprint: force
	ls pdf-gitprint/W*.pdf | $(GITCOUNT)

############################## old stuff - not used anymore
#
# rough index based on the *SUMMARY.txt
# I need to set LC_ALL otherwise grep misreads line with accents and gives truncated results
INDEX_POST= sed -e 's,\(\#\# Vid\),========== \1,'

index: force
	export LC_ALL=en_US.ISO8859-15;\
	for s in $(WEEKS); do echo ==================== $$s; \
	    ls $$s/*SUMMARY.txt | xargs egrep '(^C[0O]12AL.*txt|^NIVEAU|^\#\# Vid|^OK|^TODO|^ONGO|^NICE|^DROP)' | $(INDEX_POST) ; \
	    echo ""; \
	    echo ""; \
	    echo ""; \
	done > index.long
.PHONY: index

# all: index

#
# builds a html index of the ipynb files expected to be reachable on connect.inria.fr
# pthierry is built-in 
connect: connect.html
.PHONY: connect

connect.html: force
	tools/nbindex.py

#all: connect

