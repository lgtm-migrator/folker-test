from folker.executor.parallel_executor import ParallelExecutor
from folker.executor.sequential_executor import SequentialExecutor
from folker.load.files import load_test_files
from folker.logger import logger_factory
from folker.model.error.folker import TestSuiteResultException


def run():
    logger = logger_factory.build_system_logger()
    sequential_executor = SequentialExecutor()
    parallel_executor = ParallelExecutor()
    tests = load_test_files(logger)

    parallel_tests = [test for test in tests if test.parallel]
    sequential_tests = [test for test in tests if not test.parallel]

    executed, success, failures = 0, [], []

    success_tests, fail_tests = parallel_executor.execute(parallel_tests)
    success.extend(success_tests)
    failures.extend(fail_tests)
    executed += len(success_tests) + len(fail_tests)

    success_tests, fail_tests = sequential_executor.execute(sequential_tests)
    success.extend(success_tests)
    failures.extend(fail_tests)
    executed += len(success_tests) + len(fail_tests)

    logger.assert_execution_result(executed, success, failures)
    if len(success) is not executed:
        raise TestSuiteResultException(failures)
