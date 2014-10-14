name = node[:user]

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
  code "ssh-keygen -P '' -f /home/#{name}/.ssh/id_rsa"
  creates "/home/#{name}/.ssh/id_rsa"
end

ruby_block 'alert ssh-keys' do
  block do
    print <<-CODE

     _________________________
    |                         |
    | You have a new SSH key: |
    |   /home/*/.ssh/id_rsa   |
    |_________________________|
    (|__/) |
    ( •_•) |
    /  >  >*
CODE
  end
end
