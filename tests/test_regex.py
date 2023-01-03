from regex import check_commandline_validity, split_user_and_commandline


def test_is_valid_commandline():
    assert check_commandline_validity("python3 bla.py") is True
    assert check_commandline_validity("/usr/sbin/sshd -D") is True
    assert check_commandline_validity("$USER=bla$sshd -D") is True  # --> The $ signs are assumed to belong to the actual cmd

    assert check_commandline_validity("§user=bla§python3 bla.py") is True
    assert check_commandline_validity("§USER=bla§python3 bla.py | grep hello-world") is True
    assert check_commandline_validity("§USER=bla§sshd -D") is True

    assert check_commandline_validity("§USER=sshd -D") is False
    assert check_commandline_validity("§USER=/bla/§sshd -D") is False
    assert check_commandline_validity("§USER= bla§sshd -D") is False


def test_split_commandline():
    assert split_user_and_commandline("python3 bla.py") == (None, "python3 bla.py")
    assert split_user_and_commandline("usr/sbin/sshd -D") == (None, "usr/sbin/sshd -D")
    assert split_user_and_commandline("$USER=bla$sshd -D") == (None, "$USER=bla$sshd -D")

    assert split_user_and_commandline("§user=bla§python3 bla.py") == ("bla", "python3 bla.py")
    assert split_user_and_commandline("§USER=bla§python3 bla.py | grep hello") == ("bla", "python3 bla.py | grep hello")
    assert split_user_and_commandline("§USER=bla§sshd -D") == ("bla", "sshd -D")
