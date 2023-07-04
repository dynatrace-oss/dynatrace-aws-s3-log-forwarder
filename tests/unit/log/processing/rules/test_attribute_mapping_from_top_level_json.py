import unittest

from log.processing import LogProcessingRule


class TestAttributeMappingFromJsonProcessingRule(unittest.TestCase):
    input_message = {
        'test_attribute_1': 'test_value_1',
        'test_attribute_2': 'test_value_2',
        'test_attribute_3': 'test_value_3',
        'test_attribute_4': 'test_value_4',
    }

    def test_include_parameter(self):
        processing_rule = create_log_processing_rule({
            'include': ['test_attribute_1', 'test_attribute_3'],
            'postfix': '_mapped',
            'prefix': 'my_'
        })

        self.assertEqual(processing_rule.get_extracted_log_attributes(self.input_message), {
            'my_test_attribute_1_mapped': 'test_value_1',
            'my_test_attribute_3_mapped': 'test_value_3'
        })

    def test_exclude_parameter(self):
        processing_rule = create_log_processing_rule({
            'exclude': ['test_attribute_1', 'test_attribute_3'],
            'postfix': '_mapped',
            'prefix': 'my_'
        })

        self.assertEqual(processing_rule.get_extracted_log_attributes(self.input_message), {
            'my_test_attribute_2_mapped': 'test_value_2',
            'my_test_attribute_4_mapped': 'test_value_4'
        })

    def test_rule_validation(self):
        with self.assertRaises(ValueError):
            create_log_processing_rule(
                {
                    'include': ['test_attribute_1', 'test_attribute_3'],
                    'exclude': ['test_attribute_2', 'test_attribute_4'],
                    'postfix': '_mapped',
                    'prefix': 'my_'
                }
            )


def create_log_processing_rule(attribute_mapping):
    return LogProcessingRule(
        'name', 'source', 'pattern', 'json',
        attribute_mapping_from_json_keys=attribute_mapping,
        skip_header_lines=0
    )


if __name__ == '__main__':
    unittest.main()
