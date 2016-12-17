PROJECT := thrive-refugee
PACKAGE := esl_manager refugee_manager thrive_refugee swingtime
SOURCES := Makefile requirements.txt

VIRTUALENV := venv
CACHE := .cache
DEPENDS := $(VIRTUALENV)/.depends
INSTALLED :=$(VIRTUALENV)/.installed

ifeq ($(OS),Windows_NT)
VERSION := C:\\Python27\\python.exe
BIN := $(VIRTUALENV)/Scripts
LIB := $(VIRTUALENV)/Lib/python2.7
EXE := .exe
OPEN := cmd /c start
else
VERSION := python2.7
BIN := $(VIRTUALENV)/bin
LIB := $(VIRTUALENV)/lib/python2.7
	ifeq ($(shell uname),Linux)
	OPEN := xdg-open
	else
	OPEN := open
	endif
endif
MAN := man
SHARE := share

PYTHON := $(BIN)/python$(EXE)
PIP := $(BIN)/pip$(EXE)
PEP8 := $(BIN)/pep8$(EXE)
PYLINT := $(BIN)/pylint$(EXE)
NOSE := $(BIN)/nosetests$(EXE)

# Installation ###############################################################

.PHONY: all
all: develop

.PHONY: develop
develop: .env $(INSTALLED)
$(INSTALLED):
	$(PIP) install -r requirements.txt  --download-cache=$(CACHE)
	touch $(INSTALLED)  # flag to indicate project is installed

.PHONY: .env
.env: $(PYTHON)
$(PYTHON):
	virtualenv --python $(VERSION) $(VIRTUALENV)

.PHONY: depends
depends: .env $(DEPENDS) $(SOURCES)
$(DEPENDS):
	$(PIP) install pep8 nose coverage --download-cache=$(CACHE)
	$(MAKE) .pylint
	touch $(DEPENDS)  # flag to indicate dependencies are installed

# issue: pylint is not currently installing on Windows from PyPI
# tracker: https://bitbucket.org/logilab/pylint/issue/51
# workaround: install from the source repositories on Windows/Cygwin
.PHONY: .pylint
ifeq ($(shell uname),$(filter $(shell uname),Windows CYGWIN_NT-6.1 CYGWIN_NT-6.1-WOW64))
.pylint: .env
	$(PIP) install https://bitbucket.org/moben/logilab-common/get/cb9cb5b8fff228b9a4244e4a6d9b2464a7b6148f.zip --download-cache=$(CACHE)
	$(PIP) install https://bitbucket.org/logilab/pylint/get/8200a32b14597c24f0f4706417bf30aec1e25386.zip --download-cache=$(CACHE)
else
.pylint: .env
	$(PIP) install pylint --download-cache=$(CACHE)
endif


# Static Analysis ############################################################

.PHONY: pep8
pep8: depends
	$(PEP8) $(PACKAGE) --ignore=E501

.PHONY: pylint
pylint: depends
	$(PYLINT) $(PACKAGE) --reports no \
	                     --msg-template="{msg_id}: {msg}: {obj} line:{line}" \
	                     --max-line-length=99 \
	                     --disable=I0011,W0142,W0511,R,C

.PHONY: check
check: depends
	$(MAKE) pep8
	$(MAKE) pylint

# Testing ####################################################################

.PHONY: test
test: develop depends
	DJANGO_SETTINGS_MODULE=thrive_refugee.settings $(NOSE)

# Cleanup ####################################################################

.PHONY: .clean-env
.clean-env:
	rm -rf $(VIRTUALENV)

.PHONY: .clean-dist
.clean-dist:
	rm -rf dist build *.egg-info

.PHONY: clean
clean: .clean-env .clean-dist delete_db
	rm -rf */*.pyc */*/*.pyc */*/*/*.pyc */*/*/*/*.pyc
	rm -rf */__pycache__ */*/__pycache__ */*/*/__pycache__ */*/*/*/__pycache__
	rm -rf apidocs docs/README.html .coverage

.PHONY: clean-all
clean-all: clean
	rm -rf $(CACHE)

# Server ####################################################################

MANAGE := $(PYTHON) manage.py
DB := thrive.db

$(DB):
	$(MAKE) syncdb load_data

.PHONY: syncdb
syncdb:
	cp thrive_refugee/local_settings.default thrive_refugee/local_settings.py
	$(MANAGE) syncdb --noinput

.PHONY: load_data
load_data:
	$(MANAGE) loaddata thrive_refugee/fixtures/auth.json
	$(MANAGE) loaddata esl_manager/fixtures/eslstudent.json
	$(MANAGE) loaddata esl_manager/fixtures/attended.json
	$(MANAGE) loaddata esl_manager/fixtures/assesment.json
	$(MANAGE) loaddata refugee_manager/fixtures/volunteer.json
	$(MANAGE) loaddata refugee_manager/fixtures/case.json
	$(MANAGE) loaddata refugee_manager/fixtures/individual.json
	$(MANAGE) loaddata refugee_manager/fixtures/casedetail.json
	$(MANAGE) loaddata refugee_manager/fixtures/activitynote.json
	$(MANAGE) loaddata refugee_manager/fixtures/assessment.json
	$(MANAGE) loaddata swingtime/fixtures/eventtype.json
	$(MANAGE) loaddata swingtime/fixtures/event.json
	$(MANAGE) loaddata employment_manager/fixtures/employmentclient.json
	$(MANAGE) loaddata employment_manager/fixtures/job.json
	$(MANAGE) loaddata employment_manager/fixtures/skill.json
	$(MANAGE) loaddata employment_manager/fixtures/assesment.json
	$(MANAGE) loaddata employment_manager/fixtures/language.json

.PHONY: dump_data
dump_data:
	$(MANAGE) dumpdata auth > thrive_refugee/fixtures/auth.json
	$(MANAGE) dumpdata esl_manager.ESLStudent > esl_manager/fixtures/eslstudent.json
	$(MANAGE) dumpdata esl_manager.Attended > esl_manager/fixtures/attended.json
	$(MANAGE) dumpdata esl_manager.Assesment > esl_manager/fixtures/assesment.json
	$(MANAGE) dumpdata refugee_manager.Volunteer > refugee_manager/fixtures/volunteer.json
	$(MANAGE) dumpdata refugee_manager.Case > refugee_manager/fixtures/case.json
	$(MANAGE) dumpdata refugee_manager.Individual > refugee_manager/fixtures/individual.json
	$(MANAGE) dumpdata refugee_manager.CaseDetail > refugee_manager/fixtures/casedetail.json
	$(MANAGE) dumpdata refugee_manager.ActivityNote > refugee_manager/fixtures/activitynote.json
	$(MANAGE) dumpdata refugee_manager.Assessment > refugee_manager/fixtures/assessment.json
	$(MANAGE) dumpdata swingtime.EventType > swingtime/fixtures/eventtype.json
	$(MANAGE) dumpdata swingtime.Event > swingtime/fixtures/event.json
	$(MANAGE) dumpdata employment_manager.EmploymentClient > employment_manager/fixtures/employmentclient.json
	$(MANAGE) dumpdata employment_manager.Job > employment_manager/fixtures/job.json
	$(MANAGE) dumpdata employment_manager.Skill > employment_manager/fixtures/skill.json
	$(MANAGE) dumpdata employment_manager.Assesment > employment_manager/fixtures/assesment.json
	$(MANAGE) dumpdata employment_manager.Language > employment_manager/fixtures/language.json

.PHONY: delete_db
delete_db:
	rm -f $(DB)
	rm -f thrive_refugee/local_settings.py

.PHONY: reset_db
reset_db: delete_db syncdb load_data

.PHONY: run
run: develop $(DB) syncdb
	$(MANAGE) runserver

.PHONY: launch
launch: develop $(DB) syncdb
	eval "sleep 1; $(OPEN) http://localhost:8000" &
	$(MANAGE) runserver
