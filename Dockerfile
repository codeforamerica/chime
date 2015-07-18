FROM ubuntu:14.04

# set up basic stuff
RUN apt-get update
RUN apt-get install -y python-pip build-essential git

# set sensible environmental defaults
ENV CODE_PATH /opt/chime/webapp
ENV DATA_PATH /var/opt/chime/data/default
ENV PUBLISH_PATH /var/opt/chime/publish/default
ENV LOG_PATH /var/log/chime
ENV REPO_PATH $DATA_PATH/repo
ENV WORK_PATH $DATA_PATH/work
ENV RUNNING_STATE_DIR /var/run/chime
ENV USER chime

RUN groupadd -r $USER -g 800
RUN useradd -m -u 800 -g $USER $USER


# create necessary paths
RUN mkdir -p $CODE_PATH $DATA_PATH $PUBLISH_PATH $RUNNING_STATE_DIR $LOG_PATH
RUN chown chime:chime $DATA_PATH $PUBLISH_PATH $RUNNING_STATE_DIR $LOG_PATH

# install chime
ADD ./chime $CODE_PATH/chime
ADD ./requirements.txt $CODE_PATH/requirements.txt
ADD ./Procfile $CODE_PATH/Procfile
ADD ./setup.py $CODE_PATH/setup.py
RUN pip install -r $CODE_PATH/requirements.txt
RUN pip install -U $CODE_PATH

VOLUME $DATA_PATH
VOLUME $PUBLISH_PATH
VOLUME $LOG_PATH

# install jekyll
RUN apt-get -y install rbenv curl
ADD ./jekyll $CODE_PATH/jekyll
USER chime
RUN $CODE_PATH/jekyll/install-jekyll.sh


# app configuration
#
# TODO: make this unnecessary
ENV GA_CLIENT_ID ignored
ENV GA_CLIENT_SECRET ignored
ENV GA_REDIRECT_URI ignored
#
# TODO: rename to PERSONA_URL
ENV BROWSERID_URL "http://127.0.0.1:5000"


# TODO: remove debugging tools
USER root
RUN apt-get install psmisc strace

# make sure we are UTF-8 happy
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# set up for running the app
EXPOSE 5000
WORKDIR /opt/chime/webapp
USER chime
CMD  honcho start


# expected command-line arguments look something like
# run
#   -v /real/path/to/data:/var/opt/chime/data/default
#   -v /real/path/to/logs:/var/log/chime
#   -e 'LIVE_SITE_URL=http://127.0.0.1/'
#   -p 5000:5000

#
# The -v lines map real directories with persistent/sharable data
# to spots inside the container. the -e lines set up necessary local
# variables; feel free to override others as needed. The port mapping
# exposes the app so that you can directly use it.
