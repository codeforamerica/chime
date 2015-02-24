package 'python-pip'

name = node[:user]
github_temporary_token = ENV['GITHUB_TEMPORARY_TOKEN']

group name
user name do
  gid name
  home "/home/#{name}"
end

directory "/home/#{name}" do
  owner name
  group name
  mode "0755"
end

directory "/home/#{name}/.ssh" do
  owner name
  group name
  mode "0700"
end

directory "/var/run/#{name}" do
  owner name
  group name
  mode "0700"
end

file "/home/#{name}/.ssh/config" do
  owner name
  group name
  mode "0600"
  content "StrictHostKeyChecking no"
end

bash "ssh-keygen" do
  user name
  creates "/home/#{name}/.ssh/id_rsa.pub"
  code <<-KEYGEN
ssh-keygen -P '' -f /home/#{name}/.ssh/id_rsa
rm -f /var/run/#{name}/deploy-key.txt
KEYGEN
end

if github_temporary_token then

execute 'pip install itsdangerous'

python "sign ssh public key" do
  user name
  creates "/var/run/#{name}/deploy-key.txt"
  code <<-PUBKEY
from itsdangerous import Signer
signer = Signer('#{github_temporary_token}', salt='deploy-key')

with open('/home/#{name}/.ssh/id_rsa.pub') as file:
    pubkey = file.readline().strip()

with open('/var/run/#{name}/deploy-key.txt', 'w') as file:
    file.write(signer.sign(pubkey))
PUBKEY
end

end
