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

bash "ssh-keygen" do
  user name
  code "ssh-keygen -P '' -f /home/#{name}/.ssh/id_rsa"
  creates "/home/#{name}/.ssh/id_rsa"
end
