import pytest

from folker.module.file.action import FileStageAction, FileMethod


@pytest.mark.action_correctness
@pytest.mark.action_file
class TestFileActionValidation:
    def test_validate_empty(self):
        action = FileStageAction()

        assert not action
        assert not action.validation_report
        assert 'action.method' in action.validation_report.missing_fields
        assert 'action.file' in action.validation_report.missing_fields

    def test_validate_wrong_method(self):
        action = FileStageAction(method='X')

        assert not action
        assert not action.validation_report
        assert 'action.method' in action.validation_report.wrong_fields
        assert 'action.file' in action.validation_report.missing_fields

    def test_read_correct(self):
        action = FileStageAction(method=FileMethod.READ.name,
                                 file='a_file')

        assert action
        assert action.validation_report

    def test_write_correct(self):
        action = FileStageAction(method=FileMethod.WRITE.name,
                                 file='a_file',
                                 content='some_content')

        assert action
        assert action.validation_report

    def test_write_missing_content(self):
        action = FileStageAction(method=FileMethod.WRITE.name,
                                 file='a_file')

        assert not action
        assert not action.validation_report
        assert 'action.content' in action.validation_report.missing_fields
