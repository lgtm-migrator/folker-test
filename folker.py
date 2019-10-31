from multiprocessing import cpu_count
from multiprocessing.pool import Pool

from folker.load.files import load_test_files, load_template_files
from folker.logger import Logger
from folker.model.entity import Test
from folker.model.error.folker import TestSuiteResultException


def test_execution(test):
    test.set_logger(Logger())
    return test.execute(), test.name


def execute_parallel_test(parallel_tests: [Test]):
    pool = Pool(cpu_count())
    results = pool.map(test_execution, parallel_tests)
    pool.close()
    return [name for (result, name) in results if result], [name for (result, name) in results if not result]


def execute_sequential_tests(sequential_tests: [Test]):
    success_tests = []
    fail_tests = []
    for test in sequential_tests:
        test.set_logger(Logger())
        if test.execute():
            success_tests.append(test.name)
        else:
            fail_tests.append(test.name)

    return success_tests, fail_tests


load_template_files()
tests = load_test_files()

parallel_tests = [test for test in tests if test.parallel]
sequential_tests = [test for test in tests if not test.parallel]

executed, success, failures = 0, [], []

success_tests, fail_tests = execute_parallel_test(parallel_tests)
success.extend(success_tests)
failures.extend(fail_tests)
executed += len(success_tests) + len(fail_tests)

success_tests, fail_tests = execute_sequential_tests(sequential_tests)
success.extend(success_tests)
failures.extend(fail_tests)
executed += len(success_tests) + len(fail_tests)

Logger().assert_folker_result(executed, success, failures)
if len(success) is not executed:
    raise TestSuiteResultException(failures)
