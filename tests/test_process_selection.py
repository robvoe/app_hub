"""
This module tests the process selection, i.e. the function '__is_suitable_process'.
"""
import unittest
from run import has_suitable_commandline


class ProcessExecutable(unittest.TestCase):
    def test1(self):
        result = has_suitable_commandline(commandline="/bin/python", process_executable="/bin/python", process_args=[])
        self.assertTrue(result)

    def test2(self):
        result = has_suitable_commandline(commandline="/bin/python", process_executable="python", process_args=[])
        self.assertTrue(result)

    def test3(self):
        result = has_suitable_commandline(commandline="/bin/python", process_executable="python3", process_args=[])
        self.assertTrue(result)

    def test4(self):
        result = has_suitable_commandline(commandline="python3", process_executable="python", process_args=[])
        self.assertTrue(result)

    def test5(self):
        result = has_suitable_commandline(commandline="python", process_executable="python3", process_args=[])
        self.assertTrue(result)

    def test6(self):
        result = has_suitable_commandline(commandline="python", process_executable="python", process_args=[])
        self.assertTrue(result)

    def test7(self):
        result = has_suitable_commandline(commandline="python", process_executable="/bin/python", process_args=[])
        self.assertTrue(result)

    def test8(self):
        result = has_suitable_commandline(commandline="/etc/bin/python", process_executable="/bin/python", process_args=[])
        self.assertFalse(result)


class MoreProcessArgs(unittest.TestCase):
    def test1(self):
        result = has_suitable_commandline(commandline="python", process_executable="python", process_args=["test.py"])
        self.assertTrue(result)

    def test2(self):
        result = has_suitable_commandline(commandline="python -c test.py", process_executable="python", process_args=["-c", "test.py", "--some_arg"])
        self.assertTrue(result)


class MoreCommandlineArgs(unittest.TestCase):
    def test1(self):
        result = has_suitable_commandline(commandline="python test.py", process_executable="python", process_args=[])
        self.assertFalse(result)

    def test2(self):
        result = has_suitable_commandline(commandline="python test.py", process_executable="python", process_args=["test.py"])
        self.assertTrue(result)

    def test3(self):
        result = has_suitable_commandline(commandline="python test2.py", process_executable="python", process_args=["test.py"])
        self.assertFalse(result)


class ModifiedCommandlineArgs(unittest.TestCase):
    def test1(self):
        result = has_suitable_commandline(commandline="python /root/test.py", process_executable="python", process_args=["/root//test.py"])
        self.assertTrue(result)

    def test2(self):
        result = has_suitable_commandline(commandline="python /root//test.py", process_executable="python", process_args=["/root//test.py"])
        self.assertTrue(result)


class TestWronglyConcatenatedCommandline(unittest.TestCase):
    def test1(self):
        result = has_suitable_commandline(commandline="python/src/test.py", process_executable="python", process_args=["test.py"])
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
