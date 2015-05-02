Server install
==============

To set up a functioning Chime server:

1. Start up an Ubuntu 14.04 EC2 instance (currently using ami-d05e75b8 on a standard t2.small)
2. Set hostname: `sudo vi /etc/hostname; sudo hostname -F /etc/hostname`
    * Should be the box's public name. E.g., "test.chimecms.org" 
2. Install git: `sudo apt-get update && sudo apt-get install -y git`
3. get chime: `git clone https://github.com/codeforamerica/ceviche-cms.git`
4. run chef: `cd ceviche-cms; sudo chef/run.sh`