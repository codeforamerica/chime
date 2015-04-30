Server install
==============

To set up a functioning Chime server:

1. Start up an EC2 instance
2. Set hostname: `sudo vi /etc/hostname; sudo hostname -F /etc/hostname`
2. Install git: `sudo apt-get update && sudo apt-get install -y git`
3. get chime: `git clone https://github.com/codeforamerica/ceviche-cms.git`
4. run chef: `cd ceviche-cms; sudo chef/run.sh`