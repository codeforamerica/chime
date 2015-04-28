#!/bin/bash
if [ -d $HOME/.rbenv ]; then
  export PATH="$HOME/.rbenv/bin:$PATH"
  eval "$(rbenv init -)"
fi

RBENV_VERSION=2.2.0; export RBENV_VERSION
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BUNDLE_GEMFILE="${DIR}/Gemfile"; export BUNDLE_GEMFILE


bundle exec jekyll $*
