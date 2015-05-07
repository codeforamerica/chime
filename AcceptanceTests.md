Acceptance Tests
==============

Chime supports basic acceptance tests. Acceptance tests use [fabric](https://fabric-docs.readthedocs.org) and [selenium](https://selenium-python.readthedocs.org/)'s Firefox driver.

The simplest way to run an acceptance test is to run `fab test_chime`.

### Requirements:

**Environmental Variables for Fabric**:

+ `AWS_ACCESS_KEY`: The access ID that accompanies your Amazon IAM account. For more about Amazon IAM, please consult [here](http://aws.amazon.com/iam/).
+ `AWS_SECRET_KEY`: The secret key that accompanies your Amazon IAM account.
+ `SSH_KEY_NAME`: The filename for the private key you want to you use for SSH. NOTE: This assumes that this key lives in your `~/.ssh` directory. If it is somewhere else, you can instead set the `SSH_PRIVATE_KEY_PATH` variable with the full path to your private key file.
+ `EC2_KEY_PAIR`: The name of the keypair on AWS. This defaults to 'cfa-chime-keypair'
+ `AWS_SECURITY_GROUPS`: The name of your AWS Security Group. This defaults to 'default'

**Environmental Variables for Acceptance Tests**:

+ `TESTING_EMAIL`: Your persona email.
+ `TESTING_PASSWORD`: Your persona password.

**Python libraries**:

+ Fabric and selenium must be installed: `pip install -r fabfile/requirements.txt`

**Other**:

+ [Firefox](https://www.mozilla.org/en-US/firefox/new/)

### Available fab commands

More information about any individual fab command can be viewed by running `fab -d <command>`. You can view all fab commands with `fab -l`

+ `fab spawn_instance`: Creates a new EC2 instance and writes the public DNS to the hosts.txt file.
+ `fab despawn_instance`: Destroys an EC2 instance. Takes an optional DNS argument. If no argument is given, it will use the DNS found in the hosts.txt file.
+ `fab boot`: Spawns a new EC2 instance, writes the DNS to the hosts.txt file, and then installs the necessary requirements to start Chime running on the new instance. This can only deploy the master branch.
+ `fab test_chime`: Spawns a new EC2 instance, installs Chime, runs the tests found in `./test/selenium`, and then terminates the instance. Takes three arguments: setup, despawn, and branch:
    + setup: Flag for running the setup scripts on the instance. Defaults to True. NOTE: passing any value that is not True, true, t, or y will cause the setup script not to run.
    + despawn: Flag for despawning the instance after the tests pass. Defaults to True. NOTE: passing any value that is not True, true, t, or y will keep the instance around.
    + branch: Takes a string of a branch name. If provided, it will attempt to checkout to that branch before running the tests.
