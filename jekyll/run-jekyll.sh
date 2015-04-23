#!/bin/bash

if [ -d $HOME/.rbenv ]; then
  export RBENV_ROOT="$HOME/.rbenv"
elif [ -d /home/ubuntu/.rbenv ]; then
  export RBENV_ROOT="/home/ubuntu/.rbenv"
else
  echo "can't find rbenv; giving up"
 exit 1
fi

RBENV_VERSION=2.2.0; export RBENV_VERSION

eval "$(rbenv init -)"
export PATH="$HOME/.rbenv/bin:$PATH"

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BUNDLE_GEMFILE="${DIR}/Gemfile"; export BUNDLE_GEMFILE


bundle exec jekyll $* --config ${DIR}/govspeak_config.yml
