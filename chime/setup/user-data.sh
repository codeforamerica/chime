#!/bin/sh -ex
apt-get update -y
apt-get install -y git htop curl

# What is our public DNS name?
ipaddr=$(ifconfig eth0 | grep 'inet addr:'| grep -v '127.0.0.1' | cut -d: -f2 | awk '{{ print $1}}')
fullname=`curl -s http://169.254.169.254/latest/meta-data/public-hostname`
shortname=`echo $fullname | cut -d. -f1`

# Configure host name for Ubuntu.
sed -i '/ '$fullname'/ d' /etc/hosts
echo "$ipaddr $fullname $shortname" >> /etc/hosts
echo $shortname > /etc/hostname
hostname -F /etc/hostname

# Install Ceviche.
DIR=/var/opt/ceviche-cms
git clone -b {branch_name} https://github.com/codeforamerica/ceviche-cms.git $DIR
env \
    GA_CLIENT_ID='{ga_client_id}' GA_CLIENT_SECRET='{ga_client_secret}' \
    GITHUB_REPO='{github_repo}' GITHUB_TEMPORARY_TOKEN='{github_temporary_token}' \
    AUTH_DATA_HREF='{auth_data_href}' \
    $DIR/chef/run.sh
