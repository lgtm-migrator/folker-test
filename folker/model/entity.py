import collections
from abc import abstractmethod, ABC
from copy import copy

from folker.logger.logger import TestLogger
from folker.model.error.assertions import UnresolvableAssertionException, MalformedAssertionException, TestFailException
from folker.model.error.error import SourceException
from folker.model.error.load import InvalidSchemaDefinitionException
from folker.util.variable import replace_variables, map_variables, extract_value_from_cntext


class StageStep(ABC):
    @abstractmethod
    def execute(self, logger: TestLogger, test_context: dict, stage_context: dict) -> (dict, dict): pass

    @abstractmethod
    def enrich(self, template): pass

    @abstractmethod
    def validate(self): pass


class Action(StageStep, ABC):
    def _set_attribute_if_missing(self, template, attribute: str):
        if self.__getattribute__(attribute) is None:
            self.__setattr__(attribute, template.__getattribute__(attribute))


class StageSave(StageStep):
    save: dict

    def __init__(self, save: dict = {}) -> None:
        super().__init__()
        self.save = save if save else {}

    def __copy__(self):
        return copy(self)

    def enrich(self, template: 'StageSave'):
        new_data = {**self.save, **template.save}
        self.save = new_data

    def validate(self):
        pass

    def execute(self, logger: TestLogger, test_context: dict, stage_context: dict) -> (dict, dict):
        for (variable, saving) in self.save.items():
            variable = replace_variables(test_context, stage_context, variable)
            try:
                updated_saving, variables = map_variables(test_context, stage_context, saving)
                saving_value = eval(updated_saving)
            except Exception as e:
                saving_value = replace_variables(test_context={}, stage_context=stage_context, text=saving)

            self._resolve_variable(test_context, variable, saving_value)

        return test_context, stage_context

    def _resolve_variable(self, test_context: dict, variable, value) -> (str, object):
        variable_children = variable.split('.')

        if len(variable_children) == 1:
            test_context[variable] = value
            return

        variable_root = variable_children[0]
        variable_value = {variable_children[-1]: value}
        for element in reversed(variable_children[1:-1]):
            variable_value = {element: variable_value}

        test_context[variable_root] = self._merge_dictionaries(test_context.get(variable_root, {}), variable_value)

    def _merge_dictionaries(self, stable: dict, new_values: dict):
        if len(new_values) == 0:
            return stable
        for k, v in new_values.items():
            if (k in stable and isinstance(stable[k], dict)
                    and isinstance(new_values[k], collections.Mapping)):
                self._merge_dictionaries(stable[k], new_values[k])
            else:
                stable[k] = new_values[k]
        return stable


class StageLog(StageStep):
    logs: [str]

    def __init__(self, logs: [str] = []) -> None:
        super().__init__()
        self.logs = logs if logs else []

    def enrich(self, template: 'StageLog'):
        new_data = []
        new_data.extend(self.logs + template.logs)
        self.logs = new_data

    def validate(self):
        pass

    def execute(self, logger: TestLogger, test_context: dict, stage_context: dict) -> (dict, dict):
        for log in self.logs:
            logger.log_text(replace_variables(test_context, stage_context, log))

        return test_context, stage_context


class StageAssertions(StageStep):
    assertions: [str]

    def __init__(self, assertions: [str] = []) -> None:
        super().__init__()
        self.assertions = assertions

    def enrich(self, template: 'StageAssertions'):
        new_data = []
        new_data.extend(self.assertions + template.assertions)
        self.assertions = new_data

    def validate(self):
        pass

    def __copy__(self):
        return copy(self)

    def execute(self, logger: TestLogger, test_context: dict, stage_context: dict) -> (dict, dict):
        assertion_definitions = self.assertions

        if len(assertion_definitions) == 0:
            return test_context, stage_context

        executed, success, failures = 0, 0, []
        for assertion_definition in assertion_definitions:
            executed += 1

            assert_result = self._assert_individual(logger, assertion_definition, test_context, stage_context)

            if assert_result:
                success += 1
            else:
                failures.append(assertion_definition)

        self._wrap_up_test(logger, executed, success, failures)

        return test_context, stage_context

    def _assert_individual(self, logger: TestLogger, assertion: str, test_context: dict, stage_context: dict) -> (bool, dict):
        updated_assertion, variables = map_variables(test_context, stage_context, assertion)

        try:
            result = eval(updated_assertion)
        except Exception as e:
            logger.assertion_error(assertion=assertion, exception=e)
            raise UnresolvableAssertionException(assertion=assertion)

        if not isinstance(result, bool):
            raise MalformedAssertionException(assertion=assertion)

        if result:
            logger.assertion_success(assertion=assertion)
        else:
            logger.assertion_fail(assertion=assertion, variables=variables)

        return result

    def _wrap_up_test(self, logger: TestLogger, executed, success, failures):
        logger.assert_test_result(executed, success, executed - success)
        if success is not executed:
            raise TestFailException(failure_messages=failures)


class Stage():
    id: str
    name: str

    foreach: dict

    action: Action

    save: StageSave
    log: StageLog
    assertions: StageAssertions

    def __init__(self,
                 id: str = None,
                 name: str = None,
                 foreach: dict = {},
                 action: Action = None,
                 log: [str] = None,
                 save: dict = None,
                 assertions: [str] = [],
                 **kwargs) -> None:
        super().__init__()
        self.id = id
        self.name = name

        self.foreach = foreach

        self.action = action
        self.save = StageSave(save)
        self.log = StageLog(log)
        self.assertions = StageAssertions(assertions)

    def enrich(self, template: 'Stage'):
        if self.name is None:
            self.name = template.name

        if self.foreach != {}:
            new_data = {**self.foreach, **template.foreach}
            self.foreach = new_data

        if self.action:
            self.action.enrich(template.action)
        else:
            self.action = template.action.__copy__()
        if self.save:
            self.save.enrich(template.save)
        else:
            self.save = template.save.__copy__()
        if self.log:
            self.log.enrich(template.log)
        else:
            self.log = template.log.__copy__()
        if self.assertions:
            self.assertions.enrich(template.assertions)
        else:
            self.assertions = template.assertions.__copy__()

    def validate(self):
        if self.action is not None:
            self.action.validate()
        else:
            fields_message = '{}[name].action'.format(self.name) if self.name else '{}[id].action'.format(self.id)
            raise InvalidSchemaDefinitionException(wrong_fields=[fields_message])
        if self.save is not None:
            self.save.validate()
        if self.log is not None:
            self.log.validate()
        if self.assertions is not None:
            self.assertions.validate()

    def execute(self, logger: TestLogger, test_context: dict, stage_context: dict = {}):
        if len(self.foreach) == 0:
            return self._execute(logger, test_context, stage_context)
        else:
            key, values = self.foreach.popitem()
            values = extract_value_from_cntext(test_context, stage_context, values)

            for index, value in enumerate(values):
                updated_stage_context = {**stage_context, key: value, key + '_index': index}
                test_context = self.execute(logger, test_context, updated_stage_context)

            return test_context

    def _execute(self, logger: TestLogger, test_context: dict, stage_context: dict):
        logger.stage_start(self.name, test_context, stage_context)

        try:
            test_context, stage_context = self.action.execute(logger=logger, test_context=test_context, stage_context=stage_context)
            logger.action_executed(stage_context)
            test_context, stage_context = self.save.execute(logger=logger, test_context=test_context, stage_context=stage_context)
            test_context, stage_context = self.log.execute(logger=logger, test_context=test_context, stage_context=stage_context)
            test_context, stage_context = self.assertions.execute(logger=logger, test_context=test_context, stage_context=stage_context)
        except SourceException as e:
            e.details['stage'] = self
            raise e

        return test_context


class Test:
    id: str
    name: str
    description: str
    parallel: bool

    stages: [Stage]

    def __init__(self,
                 id: str = None,
                 name: str = 'UNDEFINED',
                 description: str = None,
                 parallel: bool = False,
                 stages: [Stage] = []
                 ) -> None:
        super().__init__()
        self.id = id
        self.name = name
        self.description = description
        self.parallel = parallel
        self.stages = stages

    def validate(self):
        missing_fields = []
        if self.name == None:
            missing_fields.append('test.name')

        if len(missing_fields) > 0:
            raise InvalidSchemaDefinitionException(missing_fields=missing_fields)

        for stage in self.stages:
            try:
                stage.validate()
            except InvalidSchemaDefinitionException as e:
                message = '{}.{}'.format(self.name, e.details['wrong_fields'][0])
                raise InvalidSchemaDefinitionException(wrong_fields=[message])

    def execute(self, logger: TestLogger, test_context: dict = None):
        if test_context is None:
            test_context = dict()

        logger.test_start(self.name, self.description)
        try:
            for stage in self.stages:
                test_context = stage.execute(logger, test_context)
        except SourceException as e:
            logger.test_finish_error(e)
            return False
        except Exception as e:
            logger.test_finish_error(e)
            return False

        logger.test_finish()

        return True
