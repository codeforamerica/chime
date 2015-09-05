from os.path import join
from multiprocessing.dummy import Pool as ThreadPool
from tempfile import mkdtemp
from unittest import TestCase

from simple_flock import SimpleFlock


def increment_file(filename):
    old = read_file(filename)
    new_val = int(old) + 1
    write_file(filename, new_val)


def write_file(filename, new_val):
    with file(filename, 'w') as f:
        f.write("{}".format(new_val))


def read_file(filename):
    with file(filename, 'r') as f:
        return f.read()


class SimpleFlockTest(TestCase):
    def setUp(self):
        self.dir = mkdtemp(prefix='simpleflocktest')
        self.lock_file = join(self.dir, 'lock')
        self.data_file = join(self.dir, 'data')
        write_file(self.data_file, 0)

    def test_serial_usage(self):
        self.assertEqual("0", read_file(self.data_file))
        with SimpleFlock(self.lock_file):
            increment_file(self.data_file)
        self.assertEqual("1", read_file(self.data_file))
        with SimpleFlock(self.lock_file):
            increment_file(self.data_file)
        self.assertEqual("2", read_file(self.data_file))
        with SimpleFlock(self.lock_file):
            increment_file(self.data_file)
            increment_file(self.data_file)
            increment_file(self.data_file)
        self.assertEqual("5", read_file(self.data_file))

    def test_parallel_usage(self):
        self.assertEqual("0", read_file(self.data_file))
        pool = ThreadPool(100)

        def do_work(ignored):
            with SimpleFlock(self.lock_file):
                increment_file(self.data_file)

        pool.map(do_work, range(0, 100))
        self.assertEqual("100", read_file(self.data_file))

    # this makes sure our testing approach really works
    def test_the_test(self):
        self.assertEqual("0", read_file(self.data_file))
        pool = ThreadPool(100)

        def do_work(ignored):
            increment_file(self.data_file)

        with self.assertRaises(ValueError):
            pool.map(do_work, range(0, 100))
        self.assertNotEqual("100", read_file(self.data_file))
