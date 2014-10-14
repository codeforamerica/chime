#!/bin/sh -e
#
# Install the chef ruby gem if chef-solo is not in the path.
# This script is safe to run multiple times.
#
if [ ! `which chef-solo` ]; then
    apt-get install -y ruby1.9.3
    gem1.9.3 install chef ohai --no-rdoc --no-ri
fi

cd `dirname $0`
chef-solo -c $PWD/solo.rb -j $PWD/role-ubuntu.json
