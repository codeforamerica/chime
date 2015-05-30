Acceptance Tests
==============

Chime supports basic acceptance tests. Acceptance tests use
[fabric](https://fabric-docs.readthedocs.org) and
[selenium](https://selenium-python.readthedocs.org/)'s Firefox driver.

The simplest way to run an acceptance test is to run `fab test_chime`.

### Requirements:

**AWS IAM Setup**:

In order to run these acceptance tests, you are first going to have to
get setup on Amazon with an [IAM account](http://aws.amazon.com/iam/):

1. Create an IAM and generate a key. This should give you values to use
  to fill in the required `AWS_ACCESS_KEY` and `AWS_SECRET_KEY`
  environmental variables below.
2. Ensure either that the user or a group the user belongs to has
  `AmazonEC2FullAccess`.
3. Create a keypair and download the .pem file. This is essentially
  interchangable with an .id-rsa file. After you download the file,
  make sure that SSH can discover it, or manually set fabric to use
  it by setting the `SSH_PRIVATE_KEY_PATH` below.

**Environmental Variables for Fabric**:

+ `AWS_ACCESS_KEY`: The access ID that accompanies your Amazon IAM
  account.
+ `AWS_SECRET_KEY`: The secret key that accompanies your Amazon IAM
  account.
+ `EC2_KEY_PAIR`: The name of the keypair on AWS. This defaults to
  'cfa-chime-keypair'
+ `AWS_SECURITY_GROUPS`: The name of your AWS Security Group. This
  defaults to 'default'
+ `SSH_PRIVATE_KEY_PATH`: This is optional. If you haven't added
  all of your keys via [ssh-add](http://linux.die.net/man/1/ssh-add)
  or another way of configuring SSH, you can use this variable to 
  describe the absolute location of the SSH keypair that you are using
  to connect to EC2.

**Environmental Variables for Acceptance Tests**:

+ `TESTING_EMAIL`: Your persona email.
+ `TESTING_PASSWORD`: Your persona password.

**Python libraries**:

+ Fabric and selenium must be installed:
  `pip install -r fabfile/requirements.txt`

**Other**:

+ [Firefox](https://www.mozilla.org/en-US/firefox/new/)

### Available fab commands

More information about any individual fab command can be viewed by
running `fab -d <command>`. You can view all fab commands with `fab -l`

+ `fab spawn_instance`: Creates a new EC2 instance and writes the
  public DNS to the hosts.txt file.
+ `fab despawn_instance`: Destroys an EC2 instance. Takes an optional
 DNS argument. If no argument is given, it will use the DNS found in
 the hosts.txt file.
+ `fab boot`: Spawns a new EC2 instance, writes the DNS to the
  hosts.txt file, and then installs the necessary requirements to start
  Chime running on the new instance. This can only deploy the master
  branch.
+ `fab test_chime`: Spawns a new EC2 instance, installs Chime, runs the
  tests found in `./test/acceptance`, and then terminates the instance.
  Takes three arguments: setup, despawn, and branch (Example:
  `fab test_chime:setup=f,despawn=f`):
    + setup: Flag for running the setup scraccipts on the instance.
      Defaults to True. NOTE: passing any value that is not True,
      true, t, or y will cause the setup script not to run.
    + despawn: Flag for despawning the instance after the tests pass.
      Defaults to True. NOTE: passing any value that is not True, true,
      t, or y will keep the instance around.
    + branch: Takes a string of a branch name. If provided, it will
      attempt to checkout to that branch before running the tests.
