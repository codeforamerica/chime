include_recipe "python"
include_recipe "account"
package "git"

#
# Put code where it needs to be.
#
git "/opt/bizarro-cms" do
  repository node['repo']
  reference node['ref']
end

execute "pip install -r requirements.txt" do
  cwd "/opt/bizarro-cms"
end

#
# Populate working directories.
#
name = node[:user]

directory "/var/opt/bizarro-work" do
  owner name
  group name
  mode "0775"
end

python "create Github repository" do
  user name
  code <<-GITHUB
import json, requests

info = dict(
    name='test-repo',
    private=False, has_issues=False, has_wiki=False, has_downloads=False
    )

url = 'https://api.github.com/orgs/ceviche/repos'
head = {'Content-Type': 'application/json'}
auth = ('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx', 'x-oauth-basic')
resp = requests.post(url, json.dumps(info), headers=head, auth=auth)
code = resp.status_code

if code == 422:
    pass # Github repository already exists
elif code not in range(200, 299):
    raise RuntimeError('Github repository creation failed, status {}'.format(code))

with open('/home/#{name}/.ssh/id_rsa.pub') as file:
    input = dict(title='test-key', key=file.read())

url = 'https://api.github.com/repos/ceviche/test-repo/keys'
resp = requests.post(url, json.dumps(input), headers=head, auth=auth)
code = resp.status_code

if code == 422:
    pass # Github deploy key already exists
elif code not in range(200, 299):
    raise RuntimeError('Github deploy key creation failed, status {}'.format(code))

GITHUB
end

bash "init bare /var/opt/bizarro-site" do
  user 'root'
  flags '-e'
  code <<-GIT
DIR=`mktemp -d /tmp/bizarro-site-XXXXXX`
git init --shared=group --bare $DIR

chown -R #{name}:#{name} $DIR
chmod -R ug+rwX $DIR
chmod -R o+rX $DIR

rm -rf /var/opt/bizarro-site
mv $DIR /var/opt/bizarro-site
GIT
end

bash "clone from codeforamerica/ceviche-starter to Github origin remote" do
  user name
  flags '-e'
  cwd '/var/opt/bizarro-site'
  code <<-GIT
git fetch https://github.com/codeforamerica/ceviche-starter.git
git branch master FETCH_HEAD

git remote add origin git@github.com:ceviche/test-repo.git
git push -u origin master
GIT
end

#
# Ensure upstart job exists.
#
env_file = File.realpath(File.join(File.dirname(__FILE__), 'honcho-env'))

execute "honcho export upstart /etc/init" do
  command "honcho -e #{env_file} export -u #{name} -a bizarro-cms upstart /etc/init"
  cwd "/opt/bizarro-cms"
end

#
# Make it go.
#
execute "stop bizarro-cms" do
  returns [0, 1]
end

execute "start bizarro-cms"
